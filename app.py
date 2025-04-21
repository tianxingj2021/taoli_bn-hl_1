from flask import Flask, render_template, jsonify, request
import asyncio
from hyperliquid import get_funding_rates as get_hl_rates
from funding_rate_monitor import FundingRateMonitor
from datetime import datetime, timedelta
import pytz
from binance_trader import BinanceTrader
from hyperliquid_trader import HyperliquidTrader
import json
from math import isnan
import aiohttp

app = Flask(__name__)
binance_monitor = FundingRateMonitor()
binance_trader = BinanceTrader()
hyperliquid_trader = HyperliquidTrader()

def calculate_binance_next_funding_time(timestamp_ms: int, symbol: str = None) -> str:
    """将币安的时间戳转换为北京时间，如果时间已过期则重新获取
    Args:
        timestamp_ms: 毫秒级时间戳，代表下次结算时间
        symbol: 交易对名称，用于重新获取结算时间
    Returns:
        str: 格式化的北京时间
    """
    try:
        # 获取当前北京时间
        current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
        
        # 将毫秒转换为秒
        timestamp_s = timestamp_ms / 1000
        # 创建UTC时间
        utc_time = datetime.fromtimestamp(timestamp_s, pytz.UTC)
        # 转换为北京时间
        beijing_time = utc_time.astimezone(pytz.timezone('Asia/Shanghai'))
        
        # 如果结算时间已过且提供了交易对名称，重新获取最新的结算时间
        if beijing_time < current_time and symbol:
            try:
                # 获取最新的资金费率信息
                latest_info = binance_trader.client.futures_mark_price(symbol=symbol)
                if latest_info and 'nextFundingTime' in latest_info:
                    new_timestamp_ms = latest_info['nextFundingTime']
                    # 递归调用，但这次不传symbol参数以避免无限循环
                    return calculate_binance_next_funding_time(new_timestamp_ms)
            except Exception as e:
                print(f"获取{symbol}最新结算时间失败: {e}")
                
        return beijing_time.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"时间转换错误: {e}")
        return "-"

def find_arbitrage_opportunities(hl_rates, binance_rates, min_diff=0.25):
    """查找套利机会"""
    opportunities = []
    
    for symbol, hl_info in hl_rates.items():
        # 移除USDT后缀以匹配币安的交易对格式
        base_symbol = symbol[:-4]
        binance_symbol = f"{base_symbol}USDT"
        
        if binance_symbol in binance_rates:
            # Hyperliquid的费率需要乘以100转换为百分比形式，但不四舍五入
            hl_rate = float(hl_info['funding_rate']) * 100
            # 将币安的资金费率保留4位小数
            binance_rate = round(binance_rates[binance_symbol].rate, 4)
            
            # 计算费率差，并保留4位小数
            rate_diff = round(hl_rate - binance_rate, 4)
            
            # 获取币安的下次结算时间
            try:
                binance_next_funding = calculate_binance_next_funding_time(binance_rates[binance_symbol].next_funding_time, binance_symbol)
                binance_funding_time = datetime.strptime(binance_next_funding, '%Y-%m-%d %H:%M:%S')
                # 将币安时间转换为带时区的时间
                binance_funding_time = pytz.timezone('Asia/Shanghai').localize(binance_funding_time)
            except:
                binance_next_funding = "-"  # 如果计算失败，显示占位符
                continue  # 如果无法获取结算时间，跳过这个交易对
            
            # 获取Hyperliquid的下次结算时间
            try:
                hl_funding_time = hl_info['next_funding_time']
                if not isinstance(hl_funding_time, datetime):
                    continue  # 如果不是有效的时间格式，跳过这个交易对
                # 确保Hyperliquid时间也是带时区的
                if hl_funding_time.tzinfo is None:
                    hl_funding_time = pytz.timezone('Asia/Shanghai').localize(hl_funding_time)
            except:
                continue
            
            # 检查费率差是否满足最小要求
            if abs(rate_diff) >= min_diff:
                # 确定哪个交易所的结算时间先到
                hl_settles_first = hl_funding_time < binance_funding_time
                
                # 确定哪个交易所的费率绝对值更大
                hl_abs_rate = abs(hl_rate)
                binance_abs_rate = abs(binance_rate)
                hl_has_bigger_rate = hl_abs_rate > binance_abs_rate
                
                strategy = ""
                if hl_rate <= 0 and binance_rate <= 0:
                    # 两个都是负费率
                    if hl_has_bigger_rate and hl_settles_first:
                        strategy = f"在Hyperliquid做多收取{hl_abs_rate}%资金费，在Binance做空支付{binance_abs_rate:.4f}%资金费"
                    elif not hl_has_bigger_rate and not hl_settles_first:
                        strategy = f"在Binance做多收取{binance_abs_rate:.4f}%资金费，在Hyperliquid做空支付{hl_abs_rate}%资金费"
                elif hl_rate >= 0 and binance_rate >= 0:
                    # 两个都是正费率
                    if hl_has_bigger_rate and hl_settles_first:
                        strategy = f"在Hyperliquid做空收取{hl_rate}%资金费，在Binance做多支付{binance_rate:.4f}%资金费"
                    elif not hl_has_bigger_rate and not hl_settles_first:
                        strategy = f"在Binance做空收取{binance_rate:.4f}%资金费，在Hyperliquid做多支付{hl_rate}%资金费"
                else:
                    # 一正一负
                    if hl_has_bigger_rate and hl_settles_first:
                        if hl_rate > 0:
                            strategy = f"在Hyperliquid做空收取{hl_rate}%资金费，在Binance做多收取{abs(binance_rate):.4f}%资金费"
                        else:
                            strategy = f"在Hyperliquid做多收取{abs(hl_rate)}%资金费，在Binance做空支付{binance_rate:.4f}%资金费"
                    elif not hl_has_bigger_rate and not hl_settles_first:
                        if binance_rate > 0:
                            strategy = f"在Binance做空收取{binance_rate:.4f}%资金费，在Hyperliquid做多收取{abs(hl_rate)}%资金费"
                        else:
                            strategy = f"在Binance做多收取{abs(binance_rate):.4f}%资金费，在Hyperliquid做空支付{hl_rate}%资金费"
                
                # 如果没有套利策略，显示"暂无套利机会"
                if not strategy:
                    strategy = "暂无套利机会"
                
                # 添加到套利机会列表
                opportunities.append({
                    'symbol': base_symbol,
                    'hl_rate': hl_rate,
                    'binance_rate': binance_rate,
                    'difference': rate_diff,
                    'next_funding_hl': hl_info['next_funding_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(hl_info['next_funding_time'], datetime) else hl_info['next_funding_time'],
                    'binance_next_funding': binance_next_funding,
                    'strategy': strategy
                })
    
    # 按费率差的绝对值排序
    opportunities.sort(key=lambda x: abs(x['difference']), reverse=True)
    return opportunities

def get_contract_counts(hl_rates, binance_rates):
    """获取两个交易所的合约数量"""
    return {
        'hyperliquid': len(hl_rates),
        'binance': len(binance_rates)
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/funding_rates')
async def get_funding_rates():
    try:
        print("开始获取资金费率数据...")
        
        # 获取 Hyperliquid 资金费率
        print("正在获取 Hyperliquid 资金费率...")
        hl_rates = await get_hl_rates()
        
        if hl_rates is None:
            print("无法获取 Hyperliquid 资金费率")
            hl_rates = {}
        elif isinstance(hl_rates, dict) and "error" in hl_rates:
            print(f"获取 Hyperliquid 资金费率出错: {hl_rates['error']}")
            hl_rates = {}
        else:
            print(f"成功获取 Hyperliquid 资金费率，合约数量: {len(hl_rates)}")
            
        # 获取 Binance 资金费率
        print("正在获取 Binance 资金费率...")
        binance_rates = await binance_monitor.get_all_funding_rates()
        
        if not binance_rates:
            print("无法获取 Binance 资金费率")
            binance_rates = {}
        else:
            print(f"成功获取 Binance 资金费率，合约数量: {len(binance_rates)}")
            
        # 处理所有合约
        all_contracts = {}
        
        # 处理 Hyperliquid 合约
        for symbol, hl_data in hl_rates.items():
            try:
                if not hl_data or not isinstance(hl_data, dict) or "funding_rate" not in hl_data:
                    print(f"跳过无效的 Hyperliquid 合约数据: {symbol}")
                    continue
                
                # 提取基础代币名称（去除USDT后缀）
                base_symbol = symbol[:-4] if symbol.endswith('USDT') else symbol
                
                # 确保funding_rate是数字
                try:
                    # Hyperliquid的费率保持原始格式
                    hl_rate = float(hl_data["funding_rate"])
                except (TypeError, ValueError):
                    print(f"无效的 Hyperliquid 费率数据: {hl_data['funding_rate']}")
                    continue
                
                # 处理next_funding_time
                if isinstance(hl_data["next_funding_time"], datetime):
                    hl_next_funding = hl_data["next_funding_time"].strftime("%Y-%m-%d %H:%M:%S")
                else:
                    try:
                        hl_next_funding = str(hl_data["next_funding_time"])
                    except:
                        hl_next_funding = None
                
                contract_info = {
                    "symbol": base_symbol,
                    "hl_rate": hl_rate,
                    "hl_next_funding": hl_next_funding,
                    "binance_rate": None,
                    "binance_next_funding": None
                }
                
                # 尝试匹配 Binance 合约
                binance_symbol = base_symbol + 'USDT'
                if binance_symbol in binance_rates:
                    bn_data = binance_rates[binance_symbol]
                    if hasattr(bn_data, 'rate') and bn_data.rate is not None:
                        try:
                            # Binance的费率已经是百分比形式，不需要再乘以100
                            contract_info["binance_rate"] = round(float(bn_data.rate), 4)
                            if hasattr(bn_data, 'next_funding_time'):
                                contract_info["binance_next_funding"] = calculate_binance_next_funding_time(bn_data.next_funding_time, binance_symbol)
                        except (TypeError, ValueError):
                            print(f"无效的 Binance 费率数据: {bn_data.rate}")
                
                all_contracts[base_symbol] = contract_info
                print(f"处理合约 {base_symbol} 完成: {contract_info}")
            except Exception as e:
                print(f"处理 Hyperliquid 合约 {symbol} 时出错: {e}")
                continue
        
        # 处理 Binance 合约
        for symbol, bn_data in binance_rates.items():
            try:
                # 提取基础代币名称（去除USDT后缀）
                base_symbol = symbol[:-4] if symbol.endswith('USDT') else symbol
                
                if base_symbol not in all_contracts:
                    try:
                        # Binance的费率已经是百分比形式，不需要再乘以100
                        binance_rate = round(float(bn_data.rate), 4) if hasattr(bn_data, 'rate') and bn_data.rate is not None else None
                        binance_next_funding = calculate_binance_next_funding_time(bn_data.next_funding_time, symbol) if hasattr(bn_data, 'next_funding_time') else None
                    except (TypeError, ValueError):
                        print(f"无效的 Binance 费率数据: {getattr(bn_data, 'rate', None)}")
                        continue
                        
                    contract_info = {
                        "symbol": base_symbol,
                        "binance_rate": binance_rate,
                        "binance_next_funding": binance_next_funding,
                        "hl_rate": None,
                        "hl_next_funding": None
                    }
                    all_contracts[base_symbol] = contract_info
            except Exception as e:
                print(f"处理 Binance 合约 {symbol} 时出错: {e}")
                continue
        
        # 计算有效合约数量
        contract_counts = {
            'hyperliquid': len([c for c in all_contracts.values() if c['hl_rate'] is not None]),
            'binance': len([c for c in all_contracts.values() if c['binance_rate'] is not None])
        }
        
        # 寻找套利机会
        opportunities = find_arbitrage_opportunities(hl_rates, binance_rates)
        
        return jsonify({
            'status': 'success',
            'data': {
                'all_contracts': all_contracts,
                'contract_counts': contract_counts,
                'opportunities': opportunities
            }
        })
        
    except Exception as e:
        print(f"获取资金费率时发生错误: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/balance', methods=['GET'])
def get_binance_balance():
    """获取币安账户余额"""
    try:
        balance = binance_trader.get_account_balance()
        return jsonify({
            'status': 'success',
            'data': {
                'balance': balance
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/position/<symbol>', methods=['GET'])
def get_binance_position(symbol):
    """获取币安指定交易对的持仓信息"""
    try:
        position = binance_trader.get_position(symbol)
        return jsonify({
            'status': 'success',
            'data': position
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/order', methods=['POST'])
def place_binance_order():
    """下单接口"""
    try:
        data = request.get_json()
        
        # 验证必需参数
        required_fields = ['symbol', 'side', 'quantity', 'leverage']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'status': 'error',
                    'message': f'缺少必需参数: {field}'
                })
        
        # 获取参数
        symbol = data['symbol']
        side = data['side']
        usdt_amount = float(data['quantity'])  # 这里的quantity实际上是USDT金额
        leverage = int(data['leverage'])
        order_type = data.get('order_type', 'MARKET')  # 修改这里的参数名
        price = float(data['price']) if 'price' in data and data['price'] else None
        
        # 调用下单函数
        response = binance_trader.place_order(
            symbol=symbol,
            side=side,
            usdt_amount=usdt_amount,  # 使用usdt_amount参数
            leverage=leverage,
            order_type=order_type,
            price=price
        )
        
        return jsonify({
            'status': 'success',
            'data': response
        })
        
    except ValueError as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/position/<symbol>/close', methods=['POST'])
def close_binance_position(symbol):
    """币安平仓接口"""
    try:
        response = binance_trader.close_position(symbol)
        if response:
            return jsonify({
                'status': 'success',
                'data': response
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '平仓失败'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/price/<symbol>', methods=['GET'])
def get_binance_price(symbol):
    """获取币安交易对的当前价格"""
    try:
        price = binance_trader.get_symbol_price(symbol)
        return jsonify({
            'status': 'success',
            'data': {
                'price': price
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/symbol_info/<symbol>', methods=['GET'])
def get_binance_symbol_info(symbol):
    """获取币安交易对的信息"""
    try:
        symbol_info = binance_trader.get_symbol_info(symbol)
        return jsonify({
            'status': 'success',
            'data': symbol_info
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/symbols', methods=['GET'])
def get_binance_symbols():
    """获取所有可交易的合约对"""
    try:
        exchange_info = binance_trader.client.futures_exchange_info()
        symbols = []
        for symbol_info in exchange_info['symbols']:
            if symbol_info['status'] == 'TRADING' and symbol_info['symbol'].endswith('USDT'):
                symbols.append({
                    'symbol': symbol_info['symbol'],
                    'baseAsset': symbol_info['baseAsset'],
                    'quoteAsset': symbol_info['quoteAsset']
                })
        
        # 按交易对名称排序
        symbols.sort(key=lambda x: x['symbol'])
        
        return jsonify({
            'status': 'success',
            'data': symbols
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/max_leverage/<symbol>', methods=['GET'])
def get_binance_max_leverage(symbol):
    """获取币安指定交易对的最大杠杆倍数"""
    try:
        max_leverage = binance_trader.get_max_leverage(symbol)
        return jsonify({
            'status': 'success',
            'data': max_leverage
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/position/close_all', methods=['POST'])
def close_all_binance_positions():
    """一键平仓所有币安持仓"""
    try:
        # 获取所有持仓
        positions = binance_trader.get_all_positions()
        
        # 遍历平仓所有有持仓量的仓位
        results = []
        for position in positions:
            if float(position['positionAmt']) != 0:  # 只平掉有仓位的
                try:
                    response = binance_trader.close_position(position['symbol'])
                    results.append({
                        'symbol': position['symbol'],
                        'status': 'success',
                        'data': response
                    })
                except Exception as e:
                    results.append({
                        'symbol': position['symbol'],
                        'status': 'error',
                        'message': str(e)
                    })
        
        return jsonify({
            'status': 'success',
            'data': results
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/position/all', methods=['GET'])
def get_all_binance_positions():
    """获取所有币安持仓"""
    try:
        positions = binance_trader.get_all_positions()
        # 过滤掉数量为0的持仓
        active_positions = [pos for pos in positions if float(pos['positionAmt']) != 0]
        return jsonify({
            'status': 'success',
            'data': active_positions
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/balance', methods=['GET'])
def get_hyperliquid_balance():
    """获取Hyperliquid账户余额"""
    try:
        balance = hyperliquid_trader.get_account_balance()
        return jsonify({
            'status': 'success',
            'data': {
                'balance': balance
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/position/<symbol>', methods=['GET'])
def get_hyperliquid_position(symbol):
    """获取Hyperliquid指定交易对的持仓信息"""
    try:
        # 移除USDT后缀
        symbol = symbol.replace('USDT', '')
        position = hyperliquid_trader.get_position(symbol)
        return jsonify({
            'status': 'success',
            'data': position
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/order', methods=['POST'])
def hyperliquid_order():
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        side = data.get('side')
        order_type = data.get('order_type', 'MARKET')
        quantity = float(data.get('quantity', 0))  # 转换为float
        price = float(data.get('price', 0)) if data.get('price') else None  # 转换为float
        usdt_amount = float(data.get('usdt_amount', 0)) if data.get('usdt_amount') else None  # 转换为float
        leverage = int(data.get('leverage', 1))

        if not all([symbol, side]):
            return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400

        if not quantity and not usdt_amount:
            return jsonify({'status': 'error', 'message': '必须指定数量或USDT金额'}), 400

        # 移除 USDT 后缀
        symbol = symbol.replace('USDT', '')

        result = hyperliquid_trader.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity if quantity else None,
            price=price,
            usdt_amount=usdt_amount,
            leverage=leverage
        )
        
        print(f"下单结果: {result}")
        
        # 如果result是字典类型且包含status字段
        if isinstance(result, dict):
            if result.get('status') == 'success' or result.get('status') == 'pending':
                return jsonify(result), 200
            else:
                return jsonify(result), 400
        else:
            return jsonify({
                'status': 'error',
                'message': str(result)
            }), 400

    except Exception as e:
        print(f"下单异常: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/hyperliquid/position/<symbol>/close', methods=['POST'])
def close_hyperliquid_position(symbol):
    """Hyperliquid平仓接口"""
    try:
        # 移除USDT后缀
        symbol = symbol.replace('USDT', '')
        response = hyperliquid_trader.close_position(symbol)
        if response:
            return jsonify({
                'status': 'success',
                'data': response
            })
        else:
            return jsonify({
                'status': 'error',
                'message': '平仓失败'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/max_leverage/<path:symbol>', methods=['GET'])
def get_hyperliquid_max_leverage(symbol):
    """获取Hyperliquid指定交易对的最大杠杆倍数"""
    try:
        # 从路径中提取基础交易对名称
        base_symbol = symbol.split('/')[0] if '/' in symbol else symbol.replace('USDC:USDC', '')
        max_leverage = hyperliquid_trader.get_max_leverage(base_symbol)
        return jsonify({
            'status': 'success',
            'data': max_leverage
        })
    except Exception as e:
        print(f"获取最大杠杆倍数失败: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/symbols', methods=['GET'])
def get_hyperliquid_symbols():
    """获取所有可交易的Hyperliquid合约对"""
    try:
        symbols = hyperliquid_trader.get_all_symbols()
        # 不再添加 USDT 后缀，因为 hyperliquid_trader.get_all_symbols() 已经返回了正确的格式
        
        return jsonify({
            'status': 'success',
            'data': symbols
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/position/close_all', methods=['POST'])
def close_all_hyperliquid_positions():
    """一键平仓所有Hyperliquid持仓"""
    try:
        # 获取所有持仓
        positions = hyperliquid_trader.get_all_positions()
        
        # 遍历平仓所有有持仓量的仓位
        results = []
        for position in positions:
            if float(position['positionAmt']) != 0:  # 只平掉有仓位的
                try:
                    response = hyperliquid_trader.close_position(position['symbol'])
                    results.append({
                        'symbol': position['symbol'],
                        'status': 'success',
                        'data': response
                    })
                except Exception as e:
                    results.append({
                        'symbol': position['symbol'],
                        'status': 'error',
                        'message': str(e)
                    })
        
        return jsonify({
            'status': 'success',
            'data': results
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/position/all', methods=['GET'])
def get_all_hyperliquid_positions():
    """获取所有Hyperliquid持仓"""
    try:
        positions = hyperliquid_trader.get_all_positions()
        # 过滤掉数量为0的持仓
        active_positions = [pos for pos in positions if float(pos['positionAmt']) != 0]
        return jsonify({
            'status': 'success',
            'data': active_positions
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/max_leverage/<symbol>', methods=['GET'])
def get_max_leverage(symbol):
    """获取两个交易所的最大杠杆"""
    try:
        # 确保symbol是正确的格式（添加USDT后缀如果没有）
        if not symbol.endswith('USDT'):
            symbol = symbol + 'USDT'
            
        print(f"获取杠杆倍数，交易对: {symbol}")  # 添加调试日志
        
        # 获取币安的最大杠杆
        try:
            binance_leverage = binance_trader.get_max_leverage(symbol)
            print(f"币安最大杠杆: {binance_leverage}")  # 添加调试日志
        except Exception as e:
            print(f"获取币安杠杆失败: {str(e)}")  # 添加调试日志
            binance_leverage = 5  # 设置默认值
            
        # 获取Hyperliquid的最大杠杆
        try:
            hyperliquid_leverage = hyperliquid_trader.get_max_leverage(symbol)
            print(f"Hyperliquid最大杠杆: {hyperliquid_leverage}")  # 添加调试日志
        except Exception as e:
            print(f"获取Hyperliquid杠杆失败: {str(e)}")  # 添加调试日志
            hyperliquid_leverage = 5  # 设置默认值
            
        return jsonify({
            'status': 'success',
            'data': {
                'binance': binance_leverage,
                'hyperliquid': hyperliquid_leverage
            }
        })
    except Exception as e:
        print(f"获取杠杆倍数失败: {str(e)}")  # 添加调试日志
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/binance/commission_rate', methods=['GET'])
def get_binance_commission_rate():
    """获取币安的交易手续费率"""
    try:
        commission_rate = binance_trader.get_commission_rate()
        return jsonify({
            'status': 'success',
            'data': commission_rate
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/hyperliquid/commission_rate', methods=['GET'])
def get_hyperliquid_commission_rate():
    """获取Hyperliquid的交易手续费率"""
    try:
        commission_rate = hyperliquid_trader.get_commission_rate()
        return jsonify({
            'status': 'success',
            'data': commission_rate
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

@app.route('/api/restart', methods=['POST'])
def restart_service():
    """重启服务"""
    try:
        # 这里可以添加重启服务的逻辑
        return jsonify({
            'status': 'success',
            'message': '服务重启成功'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)