// 工具函数
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// 创建防抖版本的refreshData
const debouncedRefresh = debounce(() => refreshData(), 300);

// 刷新币安余额
async function refreshBinanceBalance() {
    try {
        const response = await fetch('/api/binance/balance');
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('binanceBalance').textContent = `${data.data.balance.toFixed(2)} USDT`;
        } else {
            console.error('获取币安余额失败:', data.message);
        }
    } catch (error) {
        console.error('刷新币安余额出错:', error);
    }
}

// 刷新Hyperliquid余额
async function refreshHyperliquidBalance() {
    try {
        const response = await fetch('/api/hyperliquid/balance');
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('hyperliquidBalance').textContent = `${data.data.balance.toFixed(2)} USDC`;
        } else {
            console.error('获取Hyperliquid余额失败:', data.message);
        }
    } catch (error) {
        console.error('刷新Hyperliquid余额出错:', error);
    }
}

// 刷新币安持仓
async function refreshBinancePositions() {
    try {
        const response = await fetch('/api/binance/position/all');
        const data = await response.json();
        if (data.status === 'success') {
            const positionsHtml = data.data.length > 0 
                ? data.data.map(pos => {
                    const positionSize = parseFloat(pos.positionAmt);
                    const entryPrice = parseFloat(pos.entryPrice);
                    const markPrice = parseFloat(pos.markPrice);
                    const unrealizedPnL = parseFloat(pos.unrealizedProfit);
                    const side = positionSize > 0 ? '多仓' : '空仓';
                    const sideClass = positionSize > 0 ? 'text-success' : 'text-danger';
                    
                    return `
                        <div class="position-item mb-2 p-2 border rounded">
                            <div class="d-flex justify-content-between align-items-center">
                                <strong>${pos.symbol}</strong>
                                <span class="position-profit ${unrealizedPnL >= 0 ? 'text-success' : 'text-danger'}">
                                    ${unrealizedPnL.toFixed(2)} USDT
                                </span>
                            </div>
                            <div class="d-flex justify-content-between mt-1">
                                <span class="${sideClass}">${side}: ${Math.abs(positionSize).toFixed(4)}</span>
                                <span>杠杆: ${pos.leverage}x</span>
                            </div>
                            <div class="d-flex justify-content-between mt-1 small">
                                <span>开仓价: ${entryPrice.toFixed(4)}</span>
                                <span>标记价: ${markPrice.toFixed(4)}</span>
                            </div>
                        </div>
                    `;
                }).join('')
                : '<div class="text-center text-muted p-3">暂无持仓</div>';
            document.getElementById('binancePositions').innerHTML = positionsHtml;
        } else {
            console.error('获取币安持仓失败:', data.message);
            document.getElementById('binancePositions').innerHTML = '<div class="text-center text-danger">获取持仓失败</div>';
        }
    } catch (error) {
        console.error('刷新币安持仓出错:', error);
        document.getElementById('binancePositions').innerHTML = '<div class="text-center text-danger">获取持仓失败</div>';
    }
}

// 刷新Hyperliquid持仓
async function refreshHyperliquidPositions() {
    try {
        const response = await fetch('/api/hyperliquid/position/all');
        const data = await response.json();
        if (data.status === 'success') {
            const positionsHtml = data.data.length > 0
                ? data.data.map(pos => {
                    const positionSize = parseFloat(pos.positionAmt);
                    const entryPrice = parseFloat(pos.entryPrice);
                    const markPrice = parseFloat(pos.markPrice);
                    const unrealizedPnL = parseFloat(pos.unrealizedProfit);
                    const side = positionSize > 0 ? '多仓' : '空仓';
                    const sideClass = positionSize > 0 ? 'text-success' : 'text-danger';
                    
                    return `
                        <div class="position-item mb-2 p-2 border rounded">
                            <div class="d-flex justify-content-between align-items-center">
                                <strong>${pos.symbol}</strong>
                                <span class="position-profit ${unrealizedPnL >= 0 ? 'text-success' : 'text-danger'}">
                                    ${unrealizedPnL.toFixed(2)} USDC
                                </span>
                            </div>
                            <div class="d-flex justify-content-between mt-1">
                                <span class="${sideClass}">${side}: ${Math.abs(positionSize).toFixed(4)}</span>
                                <span>杠杆: ${pos.leverage}x</span>
                            </div>
                            <div class="d-flex justify-content-between mt-1 small">
                                <span>开仓价: ${entryPrice.toFixed(4)}</span>
                                <span>标记价: ${markPrice.toFixed(4)}</span>
                            </div>
                        </div>
                    `;
                }).join('')
                : '<div class="text-center text-muted p-3">暂无持仓</div>';
            document.getElementById('hyperliquidPositions').innerHTML = positionsHtml;
        } else {
            console.error('获取Hyperliquid持仓失败:', data.message);
            document.getElementById('hyperliquidPositions').innerHTML = '<div class="text-center text-danger">获取持仓失败</div>';
        }
    } catch (error) {
        console.error('刷新Hyperliquid持仓出错:', error);
        document.getElementById('hyperliquidPositions').innerHTML = '<div class="text-center text-danger">获取持仓失败</div>';
    }
}

// 获取手续费率
async function fetchCommissionRates() {
    try {
        // 获取币安手续费率
        const binanceResponse = await fetch('/api/binance/commission_rate');
        const binanceData = await binanceResponse.json();
        if (binanceData.status === 'success') {
            document.getElementById('binanceMakerFee').textContent = `${(binanceData.data.maker * 100).toFixed(3)}%`;
            document.getElementById('binanceTakerFee').textContent = `${(binanceData.data.taker * 100).toFixed(3)}%`;
        }

        // 获取Hyperliquid手续费率
        const hlResponse = await fetch('/api/hyperliquid/commission_rate');
        const hlData = await hlResponse.json();
        if (hlData.status === 'success') {
            document.getElementById('hlMakerFee').textContent = `${(hlData.data.maker * 100).toFixed(3)}%`;
            document.getElementById('hlTakerFee').textContent = `${(hlData.data.taker * 100).toFixed(3)}%`;
        }
    } catch (error) {
        console.error('获取手续费率失败:', error);
    }
}

// 刷新数据
async function refreshData() {
    try {
        console.log('开始刷新数据...');
        
        // 显示加载状态
        const arbitrageBody = document.getElementById('arbitrageOpportunities');
        const hlHighRateBody = document.getElementById('hlHighRateTokens');
        
        if (arbitrageBody) {
            arbitrageBody.innerHTML = '<tr><td colspan="8" class="text-center">数据加载中...</td></tr>';
        }
        if (hlHighRateBody) {
            hlHighRateBody.innerHTML = '<tr><td colspan="9" class="text-center">数据加载中...</td></tr>';
        }
        
        const response = await fetch('/api/funding_rates');
        const result = await response.json();
        console.log('API返回的完整数据:', result);
        
        if (result.status === 'success' && result.data && result.data.opportunities) {
            console.log('开始处理机会数据，数据长度:', result.data.opportunities.length);
            
            // 过滤并排序高费率代币
            const opportunities = result.data.opportunities;
            const highRateTokens = opportunities
                .filter(opp => {
                    const hlRate = opp && opp.hl_rate ? parseFloat(opp.hl_rate) : null;
                    return opp && 
                           typeof opp.symbol === 'string' && 
                           hlRate !== null && 
                           !isNaN(hlRate) && 
                           Math.abs(hlRate) >= 0.01; // 筛选年化费率大于1%的代币
                })
                .sort((a, b) => Math.abs(parseFloat(b.hl_rate)) - Math.abs(parseFloat(a.hl_rate)));

            console.log(`找到 ${highRateTokens.length} 个高费率代币`);
            
            // 更新高费率代币表格
            if (hlHighRateBody) {
                if (highRateTokens.length > 0) {
                    hlHighRateBody.innerHTML = highRateTokens.map((opp, index) => {
                        const hlRate = parseFloat(opp.hl_rate).toFixed(4);
                        const binanceRate = opp.binance_rate ? parseFloat(opp.binance_rate).toFixed(4) : '-';
                        const difference = opp.difference ? parseFloat(opp.difference).toFixed(4) : '-';
                        const estimatedReturn = (Math.abs(parseFloat(opp.hl_rate)) * 3).toFixed(4);
                        const nextFundingHl = opp.next_funding_hl || '-';
                        const nextFundingBinance = opp.binance_next_funding || '-';
                        
                        return `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${opp.symbol}</td>
                                <td class="${parseFloat(hlRate) >= 0 ? 'text-success' : 'text-danger'} fw-bold">${hlRate}%</td>
                                <td class="${binanceRate !== '-' && parseFloat(binanceRate) >= 0 ? 'text-success' : 'text-danger'}">${binanceRate}${binanceRate !== '-' ? '%' : ''}</td>
                                <td class="${difference !== '-' && parseFloat(difference) >= 0 ? 'text-success' : 'text-danger'}">${difference}${difference !== '-' ? '%' : ''}</td>
                                <td>${nextFundingBinance}</td>
                                <td>${nextFundingHl}</td>
                                <td>3</td>
                                <td class="text-success fw-bold">${estimatedReturn}%</td>
                            </tr>
                        `;
                    }).join('');
                    console.log('高费率代币表格更新完成');
                } else {
                    console.log('没有找到符合条件的高费率代币');
                    hlHighRateBody.innerHTML = '<tr><td colspan="9" class="text-center">暂无符合条件的高费率代币（年化费率 > 1%）</td></tr>';
                }
            } else {
                console.error('找不到高费率代币表格元素');
            }
            
            // 更新套利机会表格
            if (arbitrageBody) {
                const validOpportunities = opportunities.filter(opp => 
                    opp && 
                    typeof opp.symbol === 'string' && 
                    !isNaN(parseFloat(opp.binance_rate)) && 
                    !isNaN(parseFloat(opp.hl_rate)) && 
                    !isNaN(parseFloat(opp.difference)) &&
                    Math.abs(parseFloat(opp.difference)) >= 0.25
                );
                
                arbitrageBody.innerHTML = validOpportunities.length > 0 
                    ? validOpportunities.map((opp, index) => {
                        const binanceRate = parseFloat(opp.binance_rate).toFixed(4);
                        const hlRate = parseFloat(opp.hl_rate).toFixed(4);
                        const difference = parseFloat(opp.difference).toFixed(4);
                        return `
                            <tr>
                                <td>${index + 1}</td>
                                <td>${opp.symbol}</td>
                                <td class="${parseFloat(binanceRate) >= 0 ? 'text-success' : 'text-danger'}">${binanceRate}%</td>
                                <td class="${parseFloat(hlRate) >= 0 ? 'text-success' : 'text-danger'}">${hlRate}%</td>
                                <td class="${parseFloat(difference) >= 0 ? 'text-success' : 'text-danger'}">${difference}%</td>
                                <td>${opp.binance_next_funding || '-'}</td>
                                <td>${opp.next_funding_hl || '-'}</td>
                                <td>${opp.strategy || '暂无策略'}</td>
                            </tr>
                        `;
                    }).join('')
                    : '<tr><td colspan="8" class="text-center">暂无满足条件的套利机会</td></tr>';
            }
            
            // 更新交易对选择器
            if (result.data.all_contracts) {
                updateSymbolSelect(result.data.all_contracts);
            }
        } else {
            console.error('API返回数据格式错误:', result);
            if (arbitrageBody) {
                arbitrageBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">获取数据失败</td></tr>';
            }
            if (hlHighRateBody) {
                hlHighRateBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">获取数据失败</td></tr>';
            }
        }
    } catch (error) {
        console.error('刷新数据出错:', error);
        const arbitrageBody = document.getElementById('arbitrageOpportunities');
        const hlHighRateBody = document.getElementById('hlHighRateTokens');
        
        if (arbitrageBody) {
            arbitrageBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">获取数据失败</td></tr>';
        }
        if (hlHighRateBody) {
            hlHighRateBody.innerHTML = '<tr><td colspan="9" class="text-center text-danger">获取数据失败</td></tr>';
        }
    }
}

// 更新交易对选择器
function updateSymbolSelect(contracts) {
    try {
        const symbolSelect = document.querySelector('select[name="symbol"]');
        if (!symbolSelect) {
            console.error('找不到交易对选择器');
            return;
        }

        // 获取所有可用的交易对
        const symbols = Object.keys(contracts).sort();
        
        // 更新选择器选项
        symbolSelect.innerHTML = `
            <option value="">请选择交易对</option>
            ${symbols.map(symbol => `<option value="${symbol}">${symbol}</option>`).join('')}
        `;

        // 重新初始化Select2
        $(symbolSelect).select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: '选择或输入交易对',
            allowClear: true
        });

        console.log('交易对选择器更新完成，可用交易对:', symbols.length);
    } catch (error) {
        console.error('更新交易对选择器失败:', error);
    }
}

// 初始化下单表单
function initOrderForm() {
    try {
        // 初始化Select2
        $('.select2-symbol').select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: '选择或输入交易对',
            allowClear: true
        });

        // 初始化交易所选择
        const exchangeSelect = document.getElementById('orderExchange');
        if (exchangeSelect) {
            exchangeSelect.innerHTML = `
                <option value="">请选择交易所</option>
                <option value="binance">Binance</option>
                <option value="hyperliquid">Hyperliquid</option>
            `;
        }

        // 初始化交易方向
        const sideSelect = document.getElementById('orderSide');
        if (sideSelect) {
            sideSelect.innerHTML = `
                <option value="">请选择方向</option>
                <option value="BUY">买入</option>
                <option value="SELL">卖出</option>
            `;
        }

        // 初始化订单类型
        const typeSelect = document.getElementById('orderType');
        if (typeSelect) {
            typeSelect.innerHTML = `
                <option value="MARKET">市价单</option>
                <option value="LIMIT">限价单</option>
            `;
        }

        // 添加事件监听
        if (exchangeSelect) {
            exchangeSelect.addEventListener('change', handleExchangeChange);
        }
        if (typeSelect) {
            typeSelect.addEventListener('change', togglePriceInput);
        }

        console.log('表单初始化完成');
    } catch (error) {
        console.error('初始化表单失败:', error);
    }
}

// 执行交易
async function executeTrade(symbol, isHLLong, amount, leverage) {
    try {
        if (!confirm(`确认要执行${symbol}的套利交易吗？`)) {
            return;
        }
        
        const [binanceOrder, hlOrder] = await Promise.all([
            fetch('/api/binance/order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    symbol: symbol,
                    side: isHLLong ? 'SELL' : 'BUY',
                    quantity: amount,
                    leverage: leverage,
                    order_type: 'MARKET'
                })
            }),
            fetch('/api/hyperliquid/order', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    symbol: symbol,
                    side: isHLLong ? 'BUY' : 'SELL',
                    usdt_amount: amount,
                    leverage: leverage,
                    order_type: 'MARKET'
                })
            })
        ]);

        const [binanceResult, hlResult] = await Promise.all([
            binanceOrder.json(),
            hlOrder.json()
        ]);

        if (binanceResult.status === 'success' && hlResult.status === 'success') {
            alert('套利交易执行成功！');
            // 刷新数据
            refreshData();
            refreshBinancePositions();
            refreshHyperliquidPositions();
        } else {
            alert('交易执行失败：' + (binanceResult.message || hlResult.message));
        }
    } catch (error) {
        console.error('执行交易失败:', error);
        alert('执行交易失败: ' + error.message);
    }
}

// 刷新交易对列表
async function refreshSymbols() {
    try {
        const [binanceResponse, hlResponse] = await Promise.all([
            fetch('/api/binance/symbols'),
            fetch('/api/hyperliquid/symbols')
        ]);

        const [binanceData, hlData] = await Promise.all([
            binanceResponse.json(),
            hlResponse.json()
        ]);

        if (binanceData.status === 'success' && hlData.status === 'success') {
            const symbolSelect = document.getElementById('orderSymbol');
            symbolSelect.innerHTML = '<option value="">选择交易对</option>';
            
            // 合并两个交易所的交易对并去重
            const allSymbols = [...new Set([
                ...binanceData.data.map(s => s.symbol),
                ...hlData.data.map(s => s + 'USDT')
            ])].sort();
            
            allSymbols.forEach(symbol => {
                const option = document.createElement('option');
                option.value = symbol;
                option.textContent = symbol;
                symbolSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('刷新交易对列表失败:', error);
    }
}

// 处理交易所切换
async function handleExchangeChange() {
    const exchange = document.getElementById('orderExchange').value;
    const symbol = document.getElementById('orderSymbol').value;
    
    if (symbol) {
        try {
            const response = await fetch(`/api/${exchange}/max_leverage/${symbol}`);
            const data = await response.json();
            
            if (data.status === 'success') {
                const leverageSelect = document.getElementById('orderLeverage');
                leverageSelect.innerHTML = '';
                
                for (let i = 1; i <= data.data; i++) {
                    const option = document.createElement('option');
                    option.value = i;
                    option.textContent = `${i}x`;
                    leverageSelect.appendChild(option);
                }
            }
        } catch (error) {
            console.error('获取最大杠杆失败:', error);
        }
    }
}

// 切换价格输入框显示
function togglePriceInput() {
    const orderType = document.getElementById('orderType').value;
    const priceInputGroup = document.getElementById('priceInputGroup');
    
    if (orderType === 'LIMIT') {
        priceInputGroup.style.display = 'block';
        document.getElementById('orderPrice').required = true;
    } else {
        priceInputGroup.style.display = 'none';
        document.getElementById('orderPrice').required = false;
    }
}

// 提交订单
async function submitOrder(event) {
    event.preventDefault();
    
    const exchange = document.getElementById('orderExchange').value;
    const formData = {
        symbol: document.getElementById('orderSymbol').value,
        side: document.getElementById('orderSide').value,
        order_type: document.getElementById('orderType').value,
        leverage: parseInt(document.getElementById('orderLeverage').value),
        usdt_amount: parseFloat(document.getElementById('orderAmount').value)
    };
    
    if (formData.order_type === 'LIMIT') {
        formData.price = parseFloat(document.getElementById('orderPrice').value);
    }
    
    try {
        const response = await fetch(`/api/${exchange}/order`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            alert('下单成功！');
            // 刷新数据
            refreshData();
            refreshBinancePositions();
            refreshHyperliquidPositions();
        } else {
            alert('下单失败：' + result.message);
        }
    } catch (error) {
        console.error('下单失败:', error);
        alert('下单失败: ' + error.message);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', async function() {
    console.log('页面加载完成，开始初始化...');
    
    try {
        // 初始化表单
        initOrderForm();
        
        // 初始化其他数据
        await Promise.all([
            refreshBinanceBalance(),
            refreshHyperliquidBalance(),
            refreshBinancePositions(),
            refreshHyperliquidPositions(),
            fetchCommissionRates()
        ]);
        
        // 立即执行一次数据刷新
        await refreshData();
        
        // 设置自动刷新
        setInterval(refreshData, 60000);
        setInterval(async () => {
            await Promise.all([
                refreshBinanceBalance(),
                refreshHyperliquidBalance(),
                refreshBinancePositions(),
                refreshHyperliquidPositions()
            ]);
        }, 30000);
        
        // 添加阈值输入框事件监听
        const thresholdInput = document.getElementById('thresholdInput');
        if (thresholdInput) {
            thresholdInput.addEventListener('input', debouncedRefresh);
        }
        
        // 添加仓位比例输入框事件监听
        const positionRatioInput = document.getElementById('positionRatioInput');
        if (positionRatioInput) {
            positionRatioInput.addEventListener('input', debouncedRefresh);
        }
        
        console.log('初始化完成');
    } catch (error) {
        console.error('初始化过程中发生错误:', error);
    }
}); 