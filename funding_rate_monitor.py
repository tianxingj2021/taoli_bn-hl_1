from binance.client import Client
from binance.enums import *
import time
from datetime import datetime
import sys
from typing import Dict, List, Tuple, NamedTuple

class FundingRateInfo(NamedTuple):
    """资金费率信息"""
    rate: float
    next_funding_time: int

class FundingRateMonitor:
    def __init__(self):
        """初始化资金费率监控器"""
        self.funding_rates: Dict[str, FundingRateInfo] = {}
        self.rest_client = Client()
        
    def get_active_symbols(self) -> List[str]:
        """获取所有活跃的交易对"""
        try:
            exchange_info = self.rest_client.futures_exchange_info()
            active_symbols = [
                symbol['symbol'] for symbol in exchange_info['symbols']
                if symbol['status'] == 'TRADING'  # 只获取正在交易的交易对
            ]
            return active_symbols
        except Exception as e:
            print(f"获取活跃交易对失败: {e}")
            return []
        
    def get_funding_rates(self) -> Dict[str, FundingRateInfo]:
        """获取所有活跃交易对的当前资金费率
        
        Returns:
            Dict[str, FundingRateInfo]: 交易对到资金费率信息的映射
        """
        try:
            active_symbols = self.get_active_symbols()
            premium_index = self.rest_client.futures_mark_price()
            
            # 过滤出活跃交易对的数据
            active_data = [item for item in premium_index if item['symbol'] in active_symbols]
            sorted_data = sorted(active_data, key=lambda x: abs(float(x['lastFundingRate'])), reverse=True)
            
            # 更新资金费率
            for item in sorted_data:
                symbol = item['symbol']
                funding_rate = float(item['lastFundingRate']) * 100
                next_funding_time = int(item['nextFundingTime'])
                
                # 只有当资金费率发生变化且变化超过0.01%时才更新
                if (symbol not in self.funding_rates or 
                    abs(self.funding_rates[symbol].rate - funding_rate) > 0.01):
                    self.funding_rates[symbol] = FundingRateInfo(
                        rate=funding_rate,
                        next_funding_time=next_funding_time
                    )
                    
            return self.funding_rates
            
        except Exception as e:
            print(f"获取资金费率失败: {e}")
            return {}

    async def get_all_funding_rates(self) -> Dict[str, FundingRateInfo]:
        """异步获取所有活跃交易对的当前资金费率
        
        Returns:
            Dict[str, FundingRateInfo]: 交易对到资金费率信息的映射
        """
        try:
            # 直接调用同步方法，因为binance-python库不支持异步操作
            return self.get_funding_rates()
        except Exception as e:
            print(f"获取资金费率失败: {e}")
            return {}
        
    def get_top_rates(self, limit: int = 20) -> List[Tuple[str, FundingRateInfo]]:
        """获取资金费率最高的交易对
        
        Args:
            limit (int): 返回的交易对数量
            
        Returns:
            List[Tuple[str, FundingRateInfo]]: 按资金费率绝对值排序的交易对列表
        """
        return sorted(self.funding_rates.items(), 
                     key=lambda x: abs(x[1].rate), 
                     reverse=True)[:limit]
        
    def format_time_left(self, next_funding_time: int) -> str:
        """格式化剩余时间
        
        Args:
            next_funding_time (int): 下次结算时间戳
            
        Returns:
            str: 格式化的剩余时间
        """
        now = int(time.time() * 1000)
        time_left = (next_funding_time - now) // 1000  # 转换为秒
        
        if time_left < 0:
            return "已结算"
            
        hours = time_left // 3600
        minutes = (time_left % 3600) // 60
        seconds = time_left % 60
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
    def start_monitoring(self, update_interval: int = 3):
        """开始监控资金费率
        
        Args:
            update_interval (int): 更新间隔（秒）
        """
        print("启动U本位合约资金费率监控程序...")
        print(f"（每{update_interval}秒更新一次，只显示变化超过0.01%的更新）")
        
        while True:
            try:
                self.get_funding_rates()
                
                # 显示前20个最高的资金费率
                print("\n当前资金费率排名（按绝对值从高到低）：")
                top_rates = self.get_top_rates(20)
                for symbol, info in top_rates:
                    time_left = self.format_time_left(info.next_funding_time)
                    print(f"{symbol}: {info.rate:>10.4f}% | 下次结算: {time_left}")
                    
                time.sleep(update_interval)
                
            except KeyboardInterrupt:
                print("\n正在停止监控...")
                sys.exit(0)
                
            except Exception as e:
                print(f"监控出错: {e}")
                print("5秒后重试...")
                time.sleep(5)

def main():
    """主函数，用于直接运行此脚本"""
    monitor = FundingRateMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main() 