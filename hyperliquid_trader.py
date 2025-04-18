import os
import json
import ccxt
import time
import math
from typing import Dict, Optional, List

class HyperliquidTrader:
    def __init__(self):
        """
        初始化HyperliquidTrader类
        加载API密钥和其他配置
        """
        self.load_config()
        self.exchange = ccxt.hyperliquid({
            'apiKey': self.wallet_address,  # 使用钱包地址作为 apiKey
            'secret': self.private_key,     # 使用私钥作为 secret
            'enableRateLimit': True,
            'walletAddress': self.wallet_address,
            'privateKey': self.private_key,
        })

    def load_config(self):
        """
        从环境变量或配置文件加载私钥和钱包地址
        """
        try:
            self.private_key = os.getenv('HYPERLIQUID_PRIVATE_KEY')
            self.wallet_address = os.getenv('HYPERLIQUID_WALLET_ADDRESS')
            
            if not self.private_key or not self.wallet_address:
                config_path = os.path.join(os.path.dirname(__file__), "config.json")
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.private_key = config.get('hyperliquid_private_key')
                    self.wallet_address = config.get('account_address')
            
            if not self.private_key or not self.wallet_address:
                raise ValueError("私钥或钱包地址未配置")
                
        except Exception as e:
            raise Exception(f"加载配置失败: {str(e)}")

    def get_account_balance(self) -> float:
        """获取账户USDC余额"""
        try:
            balance = self.exchange.fetch_balance({
                'user': self.wallet_address
            })
            if 'total' in balance and 'USDC' in balance['total']:
                return float(balance['total']['USDC'])
            return 0.0
        except Exception as e:
            print(f"获取账户余额失败: {str(e)}")
            return 0.0

    def get_position(self, symbol: str) -> Dict:
        """获取指定交易对的持仓信息"""
        try:
            print(f"\n=== 开始获取持仓信息 ===")
            print(f"输入的交易对: {symbol}")
            
            # 获取所有持仓信息
            all_positions = self.exchange.fetch_positions()
            print(f"获取到所有持仓信息: {all_positions}")
            
            # 处理交易对格式
            base_symbol = symbol.split('/')[0] if '/' in symbol else symbol
            base_symbol = base_symbol.split(':')[0] if ':' in base_symbol else base_symbol
            base_symbol = base_symbol.replace('USDT', '')  # 移除USDT后缀
            
            print(f"处理后的基础币种: {base_symbol}")
            
            # 遍历所有持仓，查找匹配的持仓
            for position in all_positions:
                position_symbol = position.get('symbol', '')
                # 从position symbol中提取基础币种
                position_base = position_symbol.split('/')[0] if '/' in position_symbol else position_symbol
                position_base = position_base.split(':')[0] if ':' in position_base else position_base
                
                print(f"对比 - 持仓币种: {position_base}, 目标币种: {base_symbol}")
                
                if position_base == base_symbol:
                    print(f"找到匹配的持仓: {position}")
                    return position
            
            print(f"未找到匹配的持仓")
            return None
            
        except Exception as e:
            print(f"获取持仓信息失败: {str(e)}")
            return None

    def place_order(self, symbol, side, order_type='MARKET', quantity=None, price=None, usdt_amount=None, leverage=1, reduce_only=False):
        """
        统一下单函数
        """
        try:
            print("\n=== 开始下单 ===")
            
            # 1. 参数验证和处理
            if not symbol:
                raise ValueError("交易对不能为空")
                
            # 处理交易对格式
            base_symbol = symbol.split('/')[0] if '/' in symbol else symbol
            base_symbol = base_symbol.split(':')[0] if ':' in base_symbol else base_symbol
            formatted_symbol = f"{base_symbol}/USDC:USDC"
            
            print(f"处理后的交易对: {formatted_symbol}")
            
            # 2. 获取市场信息和价格
            market = None
            markets = self.exchange.fetch_markets()
            for m in markets:
                if m['symbol'] == formatted_symbol:
                    market = m
                    break
            
            if not market:
                raise ValueError(f"找不到交易对 {formatted_symbol} 的市场信息")
            
            # 3. 获取价格和精度信息
            current_price = self.get_symbol_price(formatted_symbol)
            print(f"当前市场价格: {current_price}")
            
            # 处理价格精度
            price_precision = int(market['precision'].get('price', 8))
            amount_precision = int(market['precision'].get('amount', 8))
            
            # 如果是限价单，使用指定价格；否则使用当前市场价
            use_price = float(format(float(price), f'.{price_precision}f')) if order_type.upper() == 'LIMIT' and price else current_price
            print(f"使用价格: {use_price}")
            
            # 4. 计算合约数量和保证金
            if quantity:
                # 如果直接指定了数量，这个数量就是USDT金额
                usdt_amount = float(quantity)
            elif usdt_amount:
                # 如果指定了USDT金额，直接使用
                usdt_amount = float(usdt_amount)
            else:
                raise ValueError("必须指定数量或USDT金额")

            # 计算合约数量
            contract_amount = usdt_amount / use_price
            print(f"计算合约数量: usdt_amount={usdt_amount}, use_price={use_price}, contract_amount={contract_amount}")
            
            # 直接使用计算出的合约数量，不进行精度调整
            quantity = contract_amount
            print(f"使用原始合约数量: quantity={quantity}")
            
            if not quantity or quantity <= 0:
                print(f"无效的下单数量: quantity={quantity}")
                raise ValueError("无效的下单数量")

            # # 重新计算实际需要的保证金
            # actual_margin = (quantity * use_price) / leverage
            # print(f"实际需要的保证金: {actual_margin} USDC")
            
            # # 检查账户余额
            # balance = self.get_account_balance()
            # print(f"当前余额: {balance} USDC")
            
            # if balance < actual_margin and not reduce_only:  # 如果是平仓单，不检查保证金
            #     return {
            #         'status': 'error',
            #         'message': f'保证金不足。需要 {actual_margin} USDC，当前余额 {balance} USDC'
            #     }

            # print(f"最终下单数量: {quantity}")
            # print(f"订单价值: {usdt_amount} USDC")
            # print(f"所需保证金: {actual_margin} USDC")

            # 7. 设置杠杆
            try:
                self.exchange.set_leverage(leverage, formatted_symbol)
                print(f"设置杠杆倍数: {leverage}")
            except Exception as e:
                print(f"设置杠杆失败: {str(e)}")
                if not reduce_only:  # 如果是平仓单，忽略设置杠杆失败的错误
                    raise e
            
            # 8. 构建订单参数
            order_params = {
                'coin': base_symbol,  # 使用基础币种名称
                'is_buy': side.upper() == 'BUY',
                'sz': str(quantity),
                'reduce_only': reduce_only  # 添加reduce_only参数
            }
            
            # 检查最小订单价值（仅对开仓单有效）
            min_order_value = 10  # 最小订单价值为10美元
            order_value = quantity * use_price
            
            # 如果是平仓单且订单价值小于最小值，调整数量
            if reduce_only and order_value < min_order_value:
                print(f"平仓单价值 ({order_value} USDC) 小于最小要求 ({min_order_value} USDC)，将调整为最小值")
                # 计算需要的最小数量
                min_quantity = math.ceil((min_order_value / use_price) * 1.01)  # 增加1%以确保满足最小值要求
                quantity = min_quantity
                order_params['sz'] = str(quantity)
                print(f"调整后的数量: {quantity}")
            elif not reduce_only and order_value < min_order_value:
                return {
                    'status': 'error',
                    'message': f'订单价值必须大于{min_order_value}美元。当前订单价值: {order_value}美元'
                }
            
            # 如果是市价单，设置滑点价格
            if order_type.upper() == 'MARKET':
                slippage = 0.05  # 5% 滑点
                if side.upper() == 'BUY':
                    slippage_price = use_price * (1 + slippage)
                else:
                    slippage_price = use_price * (1 - slippage)
                order_params['price'] = str(slippage_price)  # 使用price参数
                print(f"市价单滑点价格: {slippage_price}")
            else:
                order_params['price'] = str(use_price)
            
            print(f"最终下单参数: {order_params}")
            
            # 9. 开始下单
            print("\n开始下单...")
            
            if order_type.upper() == 'MARKET':
                order = self.exchange.create_market_order(
                    symbol=formatted_symbol,
                    side=side.lower(),
                    amount=quantity,
                    price=order_params['price'],  # 添加price参数
                    params=order_params
                )
            else:
                order = self.exchange.create_limit_order(
                    symbol=formatted_symbol,
                    side=side.lower(),
                    amount=quantity,
                    price=use_price,
                    params=order_params
                )

            # if order_type.upper() == 'LIMIT':
            #     order = self.exchange.create_limit_order(
            #         symbol=formatted_symbol,
            #         side=side.lower(),
            #         amount=quantity,
            #         price=use_price,
            #         params=order_params
            #     )
            # else:
            #     order = self.exchange.create_market_order(
            #         symbol=formatted_symbol,
            #         side=side.lower(),
            #         amount=quantity,
            #         price=order_params['price'],  # 添加price参数
            #         params=order_params
            #     )
            
            print(f"下单结果: {order}")
            return {
                'status': 'success',
                'data': order
            }
            
        except Exception as e:
            print(f"下单失败: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def close_position(self, symbol: str) -> Dict:
        """平仓指定交易对的持仓"""
        try:
            print(f"\n=== 开始平仓 {symbol} ===")
            
            # 处理交易对格式
            base_symbol = symbol.split('/')[0] if '/' in symbol else symbol
            base_symbol = base_symbol.split(':')[0] if ':' in base_symbol else base_symbol
            base_symbol = base_symbol.replace('USDT', '')  # 移除USDT后缀
            formatted_symbol = f"{base_symbol}/USDC:USDC"
            
            print(f"处理后的交易对: {formatted_symbol}")
            
            # 获取持仓信息
            position = self.get_position(symbol)
            print(f"获取到的持仓信息: {position}")
            
            if not position:
                print("未找到持仓信息")
                return {"status": "error", "message": "没有持仓"}
            
            # 从position中提取必要信息
            contracts = position.get('contracts')
            side = position.get('side')
            
            if not contracts or float(contracts) == 0:
                print("持仓数量为0")
                return {"status": "error", "message": "持仓数量为0"}
            
            if not side:
                print("无法确定持仓方向")
                return {"status": "error", "message": "无法确定持仓方向"}
            
            # 确定平仓方向和数量
            close_side = 'sell' if side == 'long' else 'buy'
            close_quantity = abs(float(contracts))
            
            print(f"准备平仓 - 交易对: {base_symbol}, 合约数量: {close_quantity}, 方向: {close_side}")
            
            # 获取当前市场价格
            current_price = self.get_symbol_price(formatted_symbol)
            slippage = 0.05  # 5% 滑点保护
            
            # 根据平仓方向设置滑点价格
            if close_side == 'buy':
                slippage_price = current_price * (1 + slippage)
            else:
                slippage_price = current_price * (1 - slippage)
            
            # 构建平仓订单参数（使用Hyperliquid的原生API格式）
            order_params = {
                'type': 'order',
                'coin': base_symbol,
                'is_buy': close_side == 'buy',
                'sz': str(close_quantity),
                'limit_px': str(slippage_price),
                'reduce_only': True,
                'order_type': {
                    'limit': {
                        'tif': 'Ioc'  # Immediate-or-cancel，类似于市价单
                    }
                }
            }
            
            print(f"下单参数: {order_params}")
            
            # 执行平仓
            try:
                order = self.exchange.create_order(
                    symbol=formatted_symbol,
                    type='limit',
                    side=close_side,
                    amount=close_quantity,
                    price=slippage_price,
                    params=order_params
                )
                print(f"平仓结果: {order}")
                return {
                    'status': 'success',
                    'data': order
                }
            except Exception as e:
                error_msg = str(e)
                print(f"平仓操作失败: {error_msg}")
                return {
                    'status': 'error',
                    'message': f"平仓失败: {error_msg}"
                }
            
        except Exception as e:
            error_msg = str(e)
            print(f"平仓失败: {error_msg}")
            return {
                'status': 'error',
                'message': f"平仓失败: {error_msg}"
            }

    def get_all_symbols(self) -> List[Dict]:
        """获取所有可交易的合约对"""
        try:
            markets = self.exchange.fetch_markets()
            return [{
                'symbol': market['symbol'],
                'baseAsset': market['base'],
                'quoteAsset': market['quote']
            } for market in markets]
        except Exception as e:
            raise Exception(f"获取交易对列表失败: {str(e)}")

    def get_market_price(self, symbol: str) -> Dict:
        """获取指定交易对的市场价格信息"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'lastPrice': float(ticker['last']),
                'volume24h': float(ticker['quoteVolume']),
                'priceChange24h': float(ticker['percentage'])
            }
        except Exception as e:
            raise Exception(f"获取市场价格失败: {str(e)}")

    def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """获取指定交易对的订单簿数据"""
        try:
            orderbook = self.exchange.fetch_order_book(symbol, limit)
            return {
                'symbol': symbol,
                'bids': orderbook['bids'][:limit],
                'asks': orderbook['asks'][:limit]
            }
        except Exception as e:
            raise Exception(f"获取订单簿数据失败: {str(e)}")

    def convert_symbol_format(self, symbol: str) -> str:
        """将币安格式的交易对转换为Hyperliquid格式
        
        Args:
            symbol: 币安格式的交易对，如 'BTCUSDT'
            
        Returns:
            str: Hyperliquid格式的交易对，如 'BTC/USDC:USDC'
        """
        try:
            # 移除USDT后缀
            base_symbol = symbol.replace('USDT', '')
            # 转换为Hyperliquid格式
            return f"{base_symbol}/USDC:USDC"
        except Exception as e:
            print(f"转换交易对格式失败: {str(e)}")
            return symbol

    def get_max_leverage(self, symbol: str) -> int:
        """获取交易对支持的最大杠杆倍数
        
        Args:
            symbol: 交易对名称，如 'BTC/USDC:USDC'
            
        Returns:
            int: 最大杠杆倍数
        """
        try:
            # 如果是币安格式，先转换为Hyperliquid格式
            if 'USDT' in symbol and '/' not in symbol:
                symbol = self.convert_symbol_format(symbol)
            
            # 从交易对名称中提取币种名称
            coin = symbol.split('/')[0]
            
            # 获取市场信息
            markets = self.exchange.fetch_markets()
            for market in markets:
                if market['symbol'] == symbol:
                    max_leverage = market['limits']['leverage']['max']
                    if max_leverage is not None:
                        return int(max_leverage)
                    break
            
            # 如果在市场信息中找不到，尝试从仓位信息中获取
            positions = self.exchange.fetch_positions([symbol])
            for position in positions:
                if position['symbol'] == symbol:
                    max_leverage = position['info']['position']['maxLeverage']
                    if max_leverage is not None:
                        return int(max_leverage)
            
            raise Exception(f"无法获取交易对 {symbol} 的最大杠杆倍数")
            
        except Exception as e:
            raise Exception(f"获取最大杠杆倍数失败: {str(e)}")

    def get_symbol_price(self, symbol: str) -> float:
        """获取交易对的当前价格"""
        try:
            print(f"开始获取{symbol}的价格...")
            # 移除USDT后缀
            base_symbol = symbol.split('/')[0] if '/' in symbol else symbol
            base_symbol = base_symbol.split(':')[0] if ':' in base_symbol else base_symbol
            base_symbol = base_symbol.replace('USDT', '')
            
            # 尝试最多3次
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    market_info = self.exchange.fetch_ticker(f"{base_symbol}/USDC:USDC")
                    if market_info and 'last' in market_info and market_info['last']:
                        print(f"获取到的价格信息: {market_info}")
                        return float(market_info['last'])
                except Exception as e:
                    print(f"第{attempt + 1}次尝试获取价格失败: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(1)  # 等待1秒后重试
                    continue
            
            raise Exception("无法获取价格信息")
        except Exception as e:
            print(f"获取价格失败: {str(e)}")
            raise Exception(f"获取价格失败: {str(e)}")

    def usd_to_contract_amount(self, symbol: str, usd_amount: float) -> float:
        """
        将USD金额转换为合约数量
        """
        try:
            price = self.get_symbol_price(symbol)
            if price <= 0:
                return 0.0
            return usd_amount / price
        except Exception as e:
            print(f"转换金额失败: {str(e)}")
            return 0.0

    def set_leverage(self, symbol: str, leverage: int) -> None:
        """设置交易对的杠杆倍数"""
        try:
            self.exchange.set_leverage(leverage, symbol)
        except Exception as e:
            raise Exception(f"设置杠杆失败: {str(e)}")

    def get_all_positions(self):
        """获取所有持仓信息"""
        try:
            positions = self.exchange.fetch_positions()
            active_positions = []
            
            for position in positions:
                contracts = position.get('contracts')
                if contracts and float(contracts) != 0:
                    # 获取基础数据
                    symbol = position.get('symbol', '').replace('/USDC:USDC', '')
                    entry_price = position.get('entryPrice')
                    mark_price = position.get('markPrice')
                    unrealized_pnl = position.get('unrealizedPnl')
                    leverage = position.get('leverage')
                    side = position.get('side')
                    notional = position.get('notional')  # 直接从CCXT返回数据中获取notional
                    
                    # 如果notional不存在，则计算
                    if not notional:
                        try:
                            contracts_float = abs(float(contracts))
                            mark_price_float = float(mark_price) if mark_price else 0.0
                            notional = contracts_float * mark_price_float
                        except (TypeError, ValueError) as e:
                            print(f"计算notional时出错: {e}")
                            notional = 0.0
                    
                    print(f"处理持仓数据 - 交易对: {symbol}, 合约数量: {contracts}, 标记价格: {mark_price}, 持仓价值: {notional}")
                    
                    # 构建标准化的持仓数据
                    position_data = {
                        'symbol': symbol,
                        'positionSide': 'LONG' if side == 'long' else 'SHORT',
                        'positionAmt': abs(float(contracts)),
                        'entryPrice': float(entry_price) if entry_price else 0.0,
                        'markPrice': float(mark_price) if mark_price else 0.0,
                        'unrealizedProfit': float(unrealized_pnl) if unrealized_pnl else 0.0,
                        'leverage': int(float(leverage)) if leverage else 1,
                        'notional': float(notional) if notional else 0.0
                    }
                    
                    print(f"添加持仓数据: {position_data}")
                    active_positions.append(position_data)
            
            return active_positions
        except Exception as e:
            print(f"获取持仓信息失败: {str(e)}")
            return []

    def get_commission_rate(self) -> Dict:
        """获取交易手续费率
        
        Returns:
            Dict: 手续费率信息，包含maker和taker费率
        """
        try:
            # Hyperliquid的手续费是固定的
            # 参考: https://hyperliquid.gitbook.io/hyperliquid/fee-schedule
            return {
                'maker': -0.0002,  # maker返佣0.02%
                'taker': 0.0005,   # taker收费0.05%
            }
        except Exception as e:
            print(f"获取手续费率失败: {str(e)}")
            raise Exception(f"获取手续费率失败: {str(e)}")