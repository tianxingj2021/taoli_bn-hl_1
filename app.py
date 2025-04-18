from flask import Flask, render_template, jsonify, request
import asyncio
from hyperliquid import get_funding_rates as get_hl_rates
from funding_rate_monitor import FundingRateMonitor
from datetime import datetime, timedelta
import pytz
from binance_trader import BinanceTrader
from hyperliquid_trader import HyperliquidTrader
import json

app = Flask(__name__)
binance_monitor = FundingRateMonitor()
binance_trader = BinanceTrader()
hyperliquid_trader = HyperliquidTrader()

def calculate_binance_next_funding_time(timestamp_ms: int) -> str:
    """将币安的时间戳转换为北京时间
    Args:
        timestamp_ms: 毫秒级时间戳，代表下次结算时间
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
        
        # 如果结算时间已过，返回占位符
        if beijing_time < current_time:
            return "-"
            
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
            # 将Hyperliquid的资金费率转换为百分比，并保留4位小数
            hl_rate = round(hl_info['funding_rate'] * 100, 4)
            # 将币安的资金费率保留4位小数
            binance_rate = round(binance_rates[binance_symbol].rate, 4)
            
            # 计算费率差，并保留4位小数
            rate_diff = round(hl_rate - binance_rate, 4)
            
            # 获取币安的下次结算时间
            try:
                binance_next_funding = calculate_binance_next_funding_time(binance_rates[binance_symbol].next_funding_time)
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
                        strategy = f"在Hyperliquid做多收取{hl_abs_rate:.4f}%资金费，在Binance做空支付{binance_abs_rate:.4f}%资金费"
                    elif not hl_has_bigger_rate and not hl_settles_first:
                        strategy = f"在Binance做多收取{binance_abs_rate:.4f}%资金费，在Hyperliquid做空支付{hl_abs_rate:.4f}%资金费"
                elif hl_rate >= 0 and binance_rate >= 0:
                    # 两个都是正费率
                    if hl_has_bigger_rate and hl_settles_first:
                        strategy = f"在Hyperliquid做空收取{hl_rate:.4f}%资金费，在Binance做多支付{binance_rate:.4f}%资金费"
                    elif not hl_has_bigger_rate and not hl_settles_first:
                        strategy = f"在Binance做空收取{binance_rate:.4f}%资金费，在Hyperliquid做多支付{hl_rate:.4f}%资金费"
                else:
                    # 一正一负
                    if hl_has_bigger_rate and hl_settles_first:
                        if hl_rate > 0:
                            strategy = f"在Hyperliquid做空收取{hl_rate:.4f}%资金费，在Binance做多收取{abs(binance_rate):.4f}%资金费"
                        else:
                            strategy = f"在Hyperliquid做多收取{abs(hl_rate):.4f}%资金费，在Binance做空支付{binance_rate:.4f}%资金费"
                    elif not hl_has_bigger_rate and not hl_settles_first:
                        if binance_rate > 0:
                            strategy = f"在Binance做空收取{binance_rate:.4f}%资金费，在Hyperliquid做多收取{abs(hl_rate):.4f}%资金费"
                        else:
                            strategy = f"在Binance做多收取{abs(binance_rate):.4f}%资金费，在Hyperliquid做空支付{hl_rate:.4f}%资金费"
                
                # 如果没有套利策略，显示"暂无套利机会"
                if not strategy:
                    strategy = "暂无套利机会"
                
                opportunities.append({
                    'symbol': base_symbol,
                    'hl_rate': hl_rate,
                    'binance_rate': binance_rate,
                    'difference': rate_diff,
                    'next_funding_hl': hl_info['next_funding_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(hl_info['next_funding_time'], datetime) else hl_info['next_funding_time'],
                    'binance_next_funding': binance_next_funding,
                    'strategy': strategy
                })
    
    return sorted(opportunities, key=lambda x: abs(x['difference']), reverse=True)

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
        # 获取当前时间
        current_time = datetime.now(pytz.timezone('Asia/Shanghai'))
        
        # 获取Hyperliquid资金费率
        hl_rates = await get_hl_rates()
        
        # 获取币安资金费率
        binance_rates = binance_monitor.get_funding_rates()
        
        # 获取合约数量
        contract_counts = get_contract_counts(hl_rates, binance_rates)
        
        # 查找套利机会
        opportunities = find_arbitrage_opportunities(hl_rates, binance_rates)
        
        # 创建完整的合约映射（包含所有可能的交易对）
        all_contracts = {}
        
        # 添加Hyperliquid的合约
        for symbol, hl_info in hl_rates.items():
            base_symbol = symbol[:-4]  # 移除USDT后缀
            next_funding_hl = hl_info['next_funding_time'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(hl_info['next_funding_time'], datetime) else hl_info['next_funding_time']
            all_contracts[base_symbol] = {
                'symbol': base_symbol,
                'hl_rate': hl_info['funding_rate'] * 100,
                'binance_rate': None,
                'next_funding_hl': next_funding_hl,
                'binance_next_funding': None,
                'difference': None
            }
        
        # 添加Binance的合约
        for symbol, info in binance_rates.items():
            if symbol.endswith('USDT'):
                base_symbol = symbol[:-4]
                try:
                    binance_next_funding = calculate_binance_next_funding_time(info.next_funding_time)
                except:
                    binance_next_funding = "-"
                    
                if base_symbol in all_contracts:
                    all_contracts[base_symbol]['binance_rate'] = info.rate
                    all_contracts[base_symbol]['binance_next_funding'] = binance_next_funding
                    all_contracts[base_symbol]['difference'] = all_contracts[base_symbol]['hl_rate'] - info.rate
                else:
                    all_contracts[base_symbol] = {
                        'symbol': base_symbol,
                        'hl_rate': None,
                        'binance_rate': info.rate,
                        'next_funding_hl': None,
                        'binance_next_funding': binance_next_funding,
                        'difference': None
                    }
        
        return jsonify({
            'status': 'success',
            'data': {
                'opportunities': opportunities,
                'contract_counts': contract_counts,
                'all_contracts': all_contracts,
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        print(f"API错误: {str(e)}")  # 添加错误日志
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
        exchange_info = binance_trader.client.exchange_info()
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
        max_leverage = hyperliquid_trader.get_max_leverage(symbol)
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
        binance_leverage = binance_trader.get_max_leverage(symbol)
        hyperliquid_leverage = hyperliquid_trader.get_max_leverage(symbol)
        return jsonify({
            'status': 'success',
            'data': {
                'binance': binance_leverage,
                'hyperliquid': hyperliquid_leverage
            }
        })
    except Exception as e:
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)