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
            "Content-Type": "application/json"
        }
        self.beijing_tz = pytz.timezone('Asia/Shanghai')

    async def get_all_contracts(self, session: aiohttp.ClientSession) -> List[str]:
        """获取所有可交易的合约列表"""
        payload = {"type": "meta"}
        try:
            async with session.post(self.base_url, headers=self.headers, json=payload) as response:
                data = await response.json()
                return [f"{item['name']}USDT" for item in data["universe"] if not item.get("isDelisted", False)]
        except Exception as e:
            print(f"获取合约列表时发生错误: {e}")
            return []

    async def get_predicted_funding_rates(self, session: aiohttp.ClientSession) -> Optional[Dict]:
        """获取所有合约的预测资金费率"""
        payload = {"type": "predictedFundings"}
        try:
            async with session.post(self.base_url, headers=self.headers, json=payload) as response:
                data = await response.json()
                predicted_rates = {}
                for item in data:
                    coin = f"{item[0]}USDT"
                    for venue in item[1]:
                        if venue[0] == "HlPerp":
                            funding_rate = float(venue[1]["fundingRate"])
                            # 获取当前时间
                            current_time = datetime.now(self.beijing_tz)
                            # 计算下一个整点时间
                            next_hour = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                            predicted_rates[coin] = {
                                "funding_rate": funding_rate,
                                "next_funding_time": next_hour
                            }
                return predicted_rates
        except Exception as e:
            print(f"获取预测资金费率时发生错误: {e}")
            return None

    async def get_all_funding_rates(self) -> Dict:
        """获取所有合约的资金费率"""
        async with aiohttp.ClientSession() as session:
            contracts = await self.get_all_contracts(session)
            if not contracts:
                return {"error": "无法获取合约列表"}

            predicted_rates = await self.get_predicted_funding_rates(session)
            if predicted_rates is None:
                return {"error": "无法获取预测费率"}

            result = {}
            for coin in contracts:
                pred_info = predicted_rates.get(coin, {})
                result[coin] = {
                    "funding_rate": pred_info.get("funding_rate", 0),
                    "next_funding_time": pred_info.get("next_funding_time", datetime.now(self.beijing_tz))
                }
            return result

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
