import os
import json
import time
import hmac
import hashlib
from binance.client import Client
from binance.enums import *
from typing import Dict, Optional, Union, List

class BinanceTrader:
    def __init__(self):
        """初始化BinanceTrader"""
        self.load_config()
        self.client = Client(api_key=self.api_key, api_secret=self.api_secret, testnet=self.testnet)
        self.ws_base_url = "wss://fstream.binance.com/ws" if not self.testnet else "wss://stream.binancefuture.com/ws"
        
        # 定义订单类型常量
        self.ORDER_TYPE_LIMIT = 'LIMIT'
        self.ORDER_TYPE_MARKET = 'MARKET'
        self.TIME_IN_FORCE_GTC = 'GTC'

    def load_config(self):
        """从环境变量或配置文件加载API密钥"""
        # 优先从环境变量获取
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')

        # 如果环境变量中没有，则从配置文件获取
        if not self.api_key or not self.api_secret:
            try:
                with open('config.json', 'r') as f:
                    config = json.load(f)
                    binance_config = config.get('binance', {})
                    self.api_key = binance_config.get('api_key')
                    self.api_secret = binance_config.get('api_secret')
                    self.testnet = binance_config.get('testnet', False)
            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                raise Exception(f"无法加载API密钥: {str(e)}")

        if not self.api_key or not self.api_secret:
            raise Exception("未找到API密钥")

    def get_account_balance(self) -> float:
        """获取账户USDT余额"""
        try:
            account_info = self.client.futures_account()
            # 获取账户总余额
            for asset in account_info['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['walletBalance'])
            return 0.0
        except Exception as e:
            error_msg = str(e)
            if 'API-key format invalid' in error_msg:
                raise Exception("API密钥格式无效，请检查API密钥是否正确配置")
            elif 'Invalid API-key' in error_msg:
                raise Exception("API密钥无效，请检查是否已正确设置API密钥")
            elif 'API-key verification failed' in error_msg:
                raise Exception("API密钥验证失败，请检查密钥是否有效且具有足够权限")
            else:
                raise Exception(f"获取账户余额失败: {error_msg}")

    def get_position(self, symbol: str) -> Optional[Dict]:
        """获取指定交易对的持仓信息
        
        Args:
            symbol: 交易对名称，如 'BTCUSDT'
            
        Returns:
            Dict: 持仓信息，包含以下字段：
                - symbol: 交易对
                - positionSide: 持仓方向 (LONG/SHORT)
                - positionAmt: 持仓数量
                - entryPrice: 开仓均价
                - unrealizedProfit: 未实现盈亏
                - leverage: 杠杆倍数
        """
        try:
            # 获取持仓风险信息
            positions = self.client.futures_position_information(symbol=symbol)
            print(f"获取到的持仓风险信息: {positions}")  # 添加调试信息
            
            # 获取当前杠杆倍数
            leverage_info = self.client.futures_leverage_bracket(symbol=symbol)
            current_leverage = int(leverage_info[0]['brackets'][0]['initialLeverage'])
            print(f"当前杠杆倍数: {current_leverage}")  # 添加调试信息
            
            for position in positions:
                if float(position['positionAmt']) != 0:  # 有持仓
                    position_amt = float(position['positionAmt'])
                    return {
                        'symbol': position['symbol'],
                        'positionSide': 'LONG' if position_amt > 0 else 'SHORT',
                        'positionAmt': abs(position_amt),
                        'entryPrice': float(position['entryPrice']),
                        'unrealizedProfit': float(position['unRealizedProfit']),
                        'leverage': current_leverage  # 使用从leverage_brackets获取的杠杆倍数
                    }
            return None
        except Exception as e:
            error_msg = str(e)
            print(f"获取持仓信息失败，错误信息: {error_msg}")  # 添加错误日志
            if 'API-key format invalid' in error_msg:
                raise Exception("API密钥格式无效，请检查API密钥是否正确配置")
            elif 'Invalid API-key' in error_msg:
                raise Exception("API密钥无效，请检查是否已正确设置API密钥")
            elif 'API-key verification failed' in error_msg:
                raise Exception("API密钥验证失败，请检查密钥是否有效且具有足够权限")
            else:
                raise Exception(f"获取持仓信息失败: {error_msg}")

    def get_symbol_info(self, symbol: str) -> Dict:
        """获取交易对的精度信息
        
        Args:
            symbol: 交易对名称，如 'BTCUSDT'
            
        Returns:
            Dict: 交易对信息，包含精度等信息
        """
        try:
            exchange_info = self.client.futures_exchange_info()
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    return {
                        'quantityPrecision': int(symbol_info['quantityPrecision']),
                        'pricePrecision': int(symbol_info['pricePrecision']),
                        'minQty': float([f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['minQty']),
                        'maxQty': float([f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['maxQty']),
                        'stepSize': float([f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'][0]['stepSize'])
                    }
            raise Exception(f"未找到交易对 {symbol} 的信息")
        except Exception as e:
            raise Exception(f"获取交易对信息失败: {str(e)}")

    def adjust_quantity(self, symbol: str, quantity: float) -> float:
        """调整数量到合法精度
        
        Args:
            symbol: 交易对名称
            quantity: 原始数量
            
        Returns:
            float: 调整后的数量
        """
        try:
            symbol_info = self.get_symbol_info(symbol)
            step_size = symbol_info['stepSize']
            precision = symbol_info['quantityPrecision']
            
            # 确保数量大于最小值
            if quantity < symbol_info['minQty']:
                raise Exception(f"数量 {quantity} 小于最小交易数量 {symbol_info['minQty']}")
            
            # 确保数量小于最大值
            if quantity > symbol_info['maxQty']:
                raise Exception(f"数量 {quantity} 大于最大交易数量 {symbol_info['maxQty']}")
            
            # 调整到步长的整数倍
            quantity = float(int(quantity / step_size) * step_size)
            
            # 处理精度
            quantity = round(quantity, precision)
            
            return quantity
        except Exception as e:
            raise Exception(f"调整数量精度失败: {str(e)}")

    def get_max_leverage(self, symbol: str) -> int:
        """获取交易对支持的最大杠杆倍数
        
        Args:
            symbol: 交易对名称，如 'BTCUSDT'
            
        Returns:
            int: 最大杠杆倍数
        """
        try:
            leverage_brackets = self.client.futures_leverage_bracket(symbol=symbol)
            # 获取第一个档位的最大杠杆
            max_leverage = int(leverage_brackets[0]['brackets'][0]['initialLeverage'])
            return max_leverage
        except Exception as e:
            raise Exception(f"获取最大杠杆倍数失败: {str(e)}")

    def place_order(self, symbol: str, side: str, quantity: float = None,
                   leverage: int = 1, order_type: str = 'MARKET',
                   price: Optional[float] = None, usdt_amount: float = None,
                   reduce_only: bool = False) -> Dict:
        """下单
        
        Args:
            symbol: 交易对名称
            side: 交易方向 ('BUY'/'SELL')
            quantity: 下单数量（以币为单位，如 BTC），与usdt_amount二选一
            leverage: 杠杆倍数
            order_type: 订单类型 ('MARKET'/'LIMIT')
            price: 限价单价格
            usdt_amount: USDT金额，与quantity二选一
            reduce_only: 是否为只减仓单
            
        Returns:
            Dict: 订单信息
        """
        try:
            # 参数验证
            if not symbol or not isinstance(symbol, str):
                raise ValueError("交易对名称无效")
            
            if side not in ['BUY', 'SELL']:
                raise ValueError("交易方向必须是 'BUY' 或 'SELL'")
            
            if order_type not in [self.ORDER_TYPE_MARKET, self.ORDER_TYPE_LIMIT]:
                raise ValueError("订单类型必须是 'MARKET' 或 'LIMIT'")
            
            if order_type == self.ORDER_TYPE_LIMIT and (not price or price <= 0):
                raise ValueError("限价单必须指定有效价格")

            if quantity is None and usdt_amount is None:
                raise ValueError("quantity和usdt_amount必须指定一个")
            
            if quantity is not None and usdt_amount is not None:
                raise ValueError("quantity和usdt_amount只能指定一个")

            if usdt_amount is not None and usdt_amount <= 0:
                raise ValueError("USDT金额必须大于0")
            
            # 准备订单参数
            order_params = {
                'symbol': symbol,
                'side': side,
                'positionSide': 'BOTH',  # 使用单向持仓模式
                'reduceOnly': reduce_only  # 添加reduceOnly参数
            }

            # 如果指定了USDT金额，使用U本位合约的下单参数
            if usdt_amount is not None:
                # 获取当前价格
                current_price = float(self.client.futures_mark_price(symbol=symbol)['markPrice'])
                # 计算合约数量（向下取整到最小精度）
                symbol_info = self.get_symbol_info(symbol)
                contract_qty = usdt_amount / current_price
                contract_qty = float(int(contract_qty * 10 ** symbol_info['quantityPrecision']) / 10 ** symbol_info['quantityPrecision'])
                order_params['quantity'] = contract_qty
            else:
                order_params['quantity'] = quantity

            # 如果是限价单，添加价格和 timeInForce
            if order_type == self.ORDER_TYPE_LIMIT:
                order_params.update({
                    'type': self.ORDER_TYPE_LIMIT,
                    'price': price,
                    'timeInForce': self.TIME_IN_FORCE_GTC
                })
            else:
                order_params['type'] = self.ORDER_TYPE_MARKET
            
            # 设置杠杆（如果需要）
            if leverage > 1:
                try:
                    self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
                except Exception as e:
                    print(f"设置杠杆失败，使用默认杠杆: {str(e)}")
            
            # 发送订单
            try:
                if order_type == self.ORDER_TYPE_MARKET:
                    response = self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type=order_type,
                        quantity=order_params['quantity'],
                        positionSide='BOTH',
                        reduceOnly=reduce_only
                    )
                else:  # LIMIT order
                    response = self.client.futures_create_order(
                        symbol=symbol,
                        side=side,
                        type=order_type,
                        quantity=order_params['quantity'],
                        positionSide='BOTH',
                        reduceOnly=reduce_only,
                        price=price,
                        timeInForce=self.TIME_IN_FORCE_GTC
                    )
                return response
            except Exception as e:
                error_msg = str(e)
                if 'insufficient balance' in error_msg.lower():
                    raise Exception("余额不足")
                elif 'price less than' in error_msg.lower():
                    raise Exception("价格太低")
                elif 'price more than' in error_msg.lower():
                    raise Exception("价格太高")
                elif 'lot size' in error_msg.lower():
                    raise Exception("数量不符合最小交易单位要求")
                elif 'maximum allowable position' in error_msg.lower():
                    raise Exception(f"当前杠杆{leverage}倍下超过最大允许持仓量")
                else:
                    raise Exception(f"下单失败: {error_msg}")
            
        except ValueError as e:
            raise Exception(str(e))
        except Exception as e:
            if isinstance(e, Exception) and str(e).startswith("下单失败"):
                raise e
            raise Exception(f"下单失败: {str(e)}")

    def close_position(self, symbol: str) -> Dict:
        """平仓指定交易对的持仓"""
        try:
            # 获取当前持仓信息
            positions = self.client.futures_position_information(symbol=symbol)
            if not positions:
                raise ValueError(f"未找到{symbol}的持仓信息")
            
            position = None
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    position = pos
                    break
                    
            if not position:
                raise ValueError("当前没有持仓")
            
            print(f"获取到的持仓信息: {position}")
            
            # 获取持仓数量和方向
            position_amt = float(position['positionAmt'])
            
            # 确定平仓方向
            side = "SELL" if position_amt > 0 else "BUY"
            
            print(f"平仓方向: {side}, 持仓数量: {abs(position_amt)}")
            
            # 执行市价平仓
            response = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=abs(position_amt),  # 使用绝对值确保数量为正
                positionSide='BOTH'  # 使用单向持仓模式
            )
            
            print(f"平仓订单响应: {response}")
            return response
            
        except Exception as e:
            print(f"平仓失败: {str(e)}")
            raise ValueError(f"平仓失败: {str(e)}")

    def get_symbol_price(self, symbol: str) -> float:
        """获取交易对的当前价格
        
        Args:
            symbol: 交易对名称，如 'BTCUSDT'
            
        Returns:
            float: 当前价格
        """
        try:
            ticker = self.client.futures_mark_price(symbol=symbol)
            return float(ticker['markPrice'])
        except Exception as e:
            error_msg = str(e)
            if 'API-key format invalid' in error_msg:
                raise Exception("API密钥格式无效，请检查API密钥是否正确配置")
            elif 'Invalid API-key' in error_msg:
                raise Exception("API密钥无效，请检查是否已正确设置API密钥")
            elif 'API-key verification failed' in error_msg:
                raise Exception("API密钥验证失败，请检查密钥是否有效且具有足够权限")
            else:
                raise Exception(f"获取价格失败: {error_msg}")

    async def get_account_status(self):
        """通过WebSocket获取账户信息"""
        try:
            import websockets
            import json
            
            # 构造请求参数
            timestamp = int(time.time() * 1000)
            params = {
                "apiKey": self.api_key,
                "timestamp": timestamp,
                "signature": self._generate_signature()
            }
            
            request = {
                "id": "605a6d20-6588-4cb9-afa0-b0ab087507ba",
                "method": "account.status",
                "params": params
            }
            
            async with websockets.connect(self.ws_base_url) as ws:
                # 发送请求
                await ws.send(json.dumps(request))
                # 接收响应
                response = await ws.recv()
                return json.loads(response)
                
        except Exception as e:
            error_msg = str(e)
            print(f"WebSocket请求失败: {error_msg}")
            raise Exception(f"获取账户信息失败: {error_msg}")

    def get_all_positions(self):
        """获取所有持仓信息"""
        try:
            print("开始获取持仓信息...")  # 添加日志
            # 使用get_position_risk获取所有持仓信息
            positions = self.client.futures_position_information()
            print(f"原始持仓数据: {positions}")  # 添加调试信息
            
            if not positions:
                print("警告：获取到的持仓数据为空")
                return []
            
            # 过滤出有持仓的仓位
            active_positions = []
            for position in positions:
                try:
                    position_amt = float(position.get('positionAmt', 0))
                    if position_amt != 0:
                        # 获取持仓信息
                        active_positions.append({
                            'symbol': position['symbol'],
                            'positionSide': 'LONG' if position_amt > 0 else 'SHORT',
                            'positionAmt': abs(position_amt),
                            'entryPrice': float(position.get('entryPrice', 0)),
                            'unrealizedProfit': float(position.get('unRealizedProfit', 0)),
                            'leverage': int(position.get('leverage', 5)),  # 默认值改为5
                            'markPrice': float(position.get('markPrice', 0)),
                            'isolatedMargin': float(position.get('isolatedMargin', 0)),
                            'notional': abs(float(position.get('notional', 0)))
                        })
                except Exception as e:
                    print(f"处理持仓数据时出错: {str(e)}, 持仓数据: {position}")
                    continue
            
            print(f"处理后的持仓数据: {active_positions}")  # 添加调试信息
            return active_positions
        except Exception as e:
            error_msg = str(e)
            print(f"获取持仓信息失败: {error_msg}")  # 保留原有的错误日志
            
            if 'API-key format invalid' in error_msg:
                raise Exception("API密钥格式无效，请检查API密钥是否正确配置")
            elif 'Invalid API-key' in error_msg:
                raise Exception("API密钥无效，请检查是否已正确设置API密钥")
            elif 'API-key verification failed' in error_msg:
                raise Exception("API密钥验证失败，请检查密钥是否有效且具有足够权限")
            elif 'Connection' in error_msg:
                raise Exception("网络连接失败，请检查网络连接")
            else:
                raise Exception(f"获取持仓信息失败: {error_msg}")

    def _generate_signature(self):
        """生成签名"""
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def get_commission_rate(self) -> Dict:
        """获取交易手续费率
        
        Returns:
            Dict: 手续费率信息，包含maker和taker费率
        """
        try:
            # 获取用户的手续费率
            commission_info = self.client.futures_commission_rate(symbol="BTCUSDT")  # 可以用任意交易对，费率是统一的
            print(f"获取到的手续费信息: {commission_info}")
            
            return {
                'maker': float(commission_info['makerCommissionRate']),  # maker费率
                'taker': float(commission_info['takerCommissionRate']),  # taker费率
            }
        except Exception as e:
            print(f"获取手续费率失败: {str(e)}")
            raise Exception(f"获取手续费率失败: {str(e)}") 