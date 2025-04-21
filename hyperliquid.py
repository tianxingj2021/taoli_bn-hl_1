import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
import pytz
from typing import Dict, List, Optional

class HyperliquidAPI:
    def __init__(self):
        self.base_url = "https://api.hyperliquid.xyz/info"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.beijing_tz = pytz.timezone('Asia/Shanghai')

    async def get_all_contracts(self, session: aiohttp.ClientSession) -> List[str]:
        """获取所有可交易的合约列表"""
        try:
            payload = {"type": "meta"}
            print(f"请求合约列表，URL: {self.base_url}")
            print(f"请求参数: {payload}")
            
            async with session.post(self.base_url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    print(f"获取合约列表失败，状态码: {response.status}")
                    return []
                    
                data = await response.json()
                print(f"获取到的合约列表原始数据: {data}")
                
                if not isinstance(data, dict) or "universe" not in data:
                    print("合约列表数据格式错误")
                    return []
                    
                contracts = [f"{item['name']}USDT" for item in data["universe"] if not item.get("isDelisted", False)]
                print(f"处理后的合约列表: {contracts}")
                return contracts
        except Exception as e:
            print(f"获取合约列表时发生错误: {e}")
            return []

    async def get_predicted_funding_rates(self, session: aiohttp.ClientSession) -> Optional[Dict]:
        """获取所有合约的预测资金费率"""
        try:
            # 首先获取所有合约
            contracts = await self.get_all_contracts(session)
            if not contracts:
                print("无法获取合约列表")
                return None
                
            print(f"开始获取资金费率，合约数量: {len(contracts)}")
            
            payload = {"type": "predictedFundings"}
            print(f"请求资金费率，URL: {self.base_url}")
            print(f"请求参数: {payload}")
            
            async with session.post(self.base_url, headers=self.headers, json=payload) as response:
                if response.status != 200:
                    print(f"获取资金费率失败，状态码: {response.status}")
                    return None
                    
                data = await response.json()
                print(f"获取到的资金费率数据长度: {len(data)}")
                
                if not isinstance(data, list):
                    print(f"资金费率数据格式错误，期望list但收到: {type(data)}")
                    return None
                    
                predicted_rates = {}
                valid_count = 0
                error_count = 0
                
                for item in data:
                    try:
                        if not isinstance(item, list) or len(item) < 2:
                            print(f"跳过无效数据项: {item}")
                            error_count += 1
                            continue
                            
                        coin = f"{item[0]}USDT"
                        if coin not in contracts:
                            print(f"跳过未知合约: {coin}")
                            error_count += 1
                            continue
                            
                        venues = item[1]
                        if not isinstance(venues, list):
                            print(f"跳过无效venue数据: {venues}")
                            error_count += 1
                            continue
                            
                        found_funding_rate = False
                        for venue in venues:
                            if not isinstance(venue, list) or len(venue) < 2:
                                continue
                                
                            if venue[0] == "HlPerp":
                                try:
                                    venue_data = venue[1]
                                    if not isinstance(venue_data, dict) or "fundingRate" not in venue_data:
                                        print(f"合约 {coin} 的资金费率数据无效: {venue_data}")
                                        continue
                                        
                                    funding_rate = float(venue_data["fundingRate"])
                                    
                                    # 获取当前时间
                                    current_time = datetime.now(self.beijing_tz)
                                    # 计算下一个整点时间
                                    next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                                    
                                    predicted_rates[coin] = {
                                        "funding_rate": funding_rate,
                                        "next_funding_time": next_hour
                                    }
                                    valid_count += 1
                                    found_funding_rate = True
                                    print(f"成功获取{coin}的资金费率: {funding_rate}")
                                except (ValueError, TypeError, KeyError) as e:
                                    print(f"处理{coin}的资金费率时出错: {str(e)}")
                                    error_count += 1
                                    continue
                                    
                        if not found_funding_rate:
                            print(f"未找到{coin}的资金费率数据")
                            error_count += 1
                            
                    except Exception as e:
                        print(f"处理数据项时出错: {str(e)}")
                        error_count += 1
                        continue
                    
                print(f"资金费率处理统计:")
                print(f"- 成功处理的合约数量: {valid_count}")
                print(f"- 处理失败的合约数量: {error_count}")
                print(f"- 总合约数量: {len(data)}")
                
                if valid_count == 0:
                    print("警告：没有成功处理任何合约的资金费率")
                    return None
                    
                return predicted_rates
                
        except Exception as e:
            print(f"获取预测资金费率时发生错误: {e}")
            return None

    async def get_all_funding_rates(self) -> Dict:
        """获取所有合约的资金费率"""
        try:
            async with aiohttp.ClientSession() as session:
                predicted_rates = await self.get_predicted_funding_rates(session)
                if predicted_rates is None:
                    print("无法获取预测费率")
                    return {"error": "无法获取合约列表"}

                print(f"获取到 {len(predicted_rates)} 个合约的资金费率")
                return predicted_rates
        except Exception as e:
            print(f"获取资金费率时发生错误: {e}")
            return {"error": str(e)}

    def format_funding_rates(self, rates: Dict) -> str:
        """格式化资金费率信息为字符串"""
        if "error" in rates:
            return rates["error"]

        output = ["\n所有合约预测资金费率信息:", "-" * 80]
        output.append(f"{'合约':<15} {'预测费率':<15} {'下次结算时间':<25}")
        output.append("-" * 80)

        for coin, info in rates.items():
            pred_rate = f"{info['funding_rate'] * 100:.4f}%"
            next_time = info['next_funding_time'].strftime('%Y-%m-%d %H:%M:%S')
            output.append(f"{coin:<15} {pred_rate:<15} {next_time:<25}")

        return "\n".join(output)

async def get_funding_rates() -> Dict:
    """获取所有合约资金费率的便捷函数"""
    api = HyperliquidAPI()
    return await api.get_all_funding_rates()

def print_funding_rates(rates: Dict) -> None:
    """打印资金费率信息的便捷函数"""
    api = HyperliquidAPI()
    print(api.format_funding_rates(rates))

if __name__ == "__main__":
    async def main():
        rates = await get_funding_rates()
        print_funding_rates(rates)

    asyncio.run(main())
