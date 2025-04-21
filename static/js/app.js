// 工具函数
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// 刷新账户余额
async function refreshBalances() {
    try {
        // 获取币安余额
        const bnResponse = await fetch('/api/binance/balance');
        const bnData = await bnResponse.json();
        if (bnData.status === 'success') {
            document.getElementById('binanceBalance').textContent = `${bnData.data.balance.toFixed(2)} USDT`;
        }

        // 获取Hyperliquid余额
        const hlResponse = await fetch('/api/hyperliquid/balance');
        const hlData = await hlResponse.json();
        if (hlData.status === 'success') {
            document.getElementById('hyperliquidBalance').textContent = `${hlData.data.balance.toFixed(2)} USDC`;
        }
    } catch (error) {
        console.error('刷新余额失败:', error);
    }
}

// 格式化费率
function formatRate(rate, decimals = 4, showSign = true) {
    if (rate === null || rate === undefined || isNaN(rate)) {
        return '-';
    }
    const absRate = Math.abs(Number(rate));
    const formattedRate = absRate.toFixed(decimals);
    return showSign ? (rate >= 0 ? `+${formattedRate}%` : `-${formattedRate}%`) : `${formattedRate}%`;
}

// 获取费率颜色类
function getColorClass(rate, isSettlementRate = false) {
    if (rate === null || rate === undefined || isNaN(rate)) {
        return '';
    }
    if (isSettlementRate) {
        return Math.abs(rate) >= 0.0025 ? 'text-danger' : '';
    }
    return rate > 0 ? 'text-success' : rate < 0 ? 'text-danger' : '';
}

// 格式化日期时间
function formatDateTime(dateStr) {
    if (!dateStr || dateStr === '-') {
        return '-';
    }
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            return dateStr;
        }
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    } catch (e) {
        return dateStr;
    }
}

// 处理费率数据
function processRateData(rate) {
    if (rate === null || rate === undefined || isNaN(rate)) {
        return null;
    }
    return Number(rate);
}

// 格式化数字的工具函数
function formatNumber(number, decimals = 4) {
    if (number === null || number === undefined || number === 'null' || number === '' || isNaN(Number(number))) {
        return '-';
    }
    return Number(number).toFixed(decimals);
}

// 刷新资金费率数据
async function refreshFundingRates() {
    try {
        console.log("开始获取资金费率数据...");
        const loadingStatus = document.getElementById('loadingStatus');
        if (loadingStatus) {
            loadingStatus.style.display = 'block';
        }

        // 检查是否需要立即刷新
        const now = new Date();
        const currentMinute = now.getMinutes();
        const currentSecond = now.getSeconds();
        
        // 如果当前时间在结算时间点后的5分钟内，立即刷新
        if (currentMinute <= 5) {
            console.log("检测到可能刚过结算时间，立即刷新数据...");
            await fetch('/api/refresh_funding_rates');
        }
        
        const response = await fetch('/api/funding_rates');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        
        console.log("API响应数据:", result);
        
        if (!result || result.status !== 'success' || !result.data) {
            throw new Error(result.message || '获取数据失败');
        }
        
        // 更新合约数量
        const contractCounts = result.data.contract_counts || { hyperliquid: 0, binance: 0 };
        const hlContractCount = document.getElementById('hlContractCount');
        const binanceContractCount = document.getElementById('binanceContractCount');
        if (hlContractCount) hlContractCount.textContent = contractCounts.hyperliquid || 0;
        if (binanceContractCount) binanceContractCount.textContent = contractCounts.binance || 0;
        
        // 更新高费率代币表格
        if (result.data.all_contracts) {
            updateHighRateTokensTable(result.data.all_contracts);
        } else {
            console.error('缺少all_contracts数据');
            const hlHighRateTokens = document.getElementById('hlHighRateTokens');
            if (hlHighRateTokens) {
                hlHighRateTokens.innerHTML = '<tr><td colspan="9" class="text-center">暂无数据</td></tr>';
            }
        }
        
        // 更新套利机会表格
        if (result.data.opportunities) {
            updateArbitrageTable(result.data.opportunities);
        } else {
            console.error('缺少opportunities数据');
            const arbitrageOpportunities = document.getElementById('arbitrageOpportunities');
            if (arbitrageOpportunities) {
                arbitrageOpportunities.innerHTML = '<tr><td colspan="8" class="text-center">暂无套利机会</td></tr>';
            }
        }
        
        if (loadingStatus) {
            loadingStatus.style.display = 'none';
        }
        const lastUpdate = document.getElementById('lastUpdate');
        if (lastUpdate) {
            lastUpdate.textContent = new Date().toLocaleString('zh-CN');
        }
        
    } catch (error) {
        console.error("获取资金费率数据失败:", error);
        const elements = {
            loadingStatus: document.getElementById('loadingStatus'),
            hlContractCount: document.getElementById('hlContractCount'),
            binanceContractCount: document.getElementById('binanceContractCount'),
            hlHighRateTokens: document.getElementById('hlHighRateTokens'),
            arbitrageOpportunities: document.getElementById('arbitrageOpportunities')
        };
        
        if (elements.loadingStatus) elements.loadingStatus.style.display = 'none';
        if (elements.hlContractCount) elements.hlContractCount.textContent = '0';
        if (elements.binanceContractCount) elements.binanceContractCount.textContent = '0';
        if (elements.hlHighRateTokens) {
            elements.hlHighRateTokens.innerHTML = '<tr><td colspan="9" class="text-center">获取数据失败</td></tr>';
        }
        if (elements.arbitrageOpportunities) {
            elements.arbitrageOpportunities.innerHTML = '<tr><td colspan="8" class="text-center">获取数据失败</td></tr>';
        }
    }
}

// 计算结算次数
function calculateSettlementCount(nextFundingTime) {
    if (!nextFundingTime || nextFundingTime === '-') {
        return 0;
    }
    try {
        const now = new Date();
        const nextFunding = new Date(nextFundingTime);
        if (isNaN(nextFunding.getTime())) {
            return 0;
        }
        
        // 如果下次结算时间已经过了，返回0
        if (nextFunding <= now) {
            return 0;
        }
        
        // 获取当前小时和结算小时
        const currentHour = now.getHours();
        const fundingHour = nextFunding.getHours();
        
        // 如果是同一天
        if (nextFunding.getDate() === now.getDate()) {
            return Math.max(0, fundingHour - currentHour - 1);
        }
        
        // 如果是第二天
        if (nextFunding.getDate() === now.getDate() + 1) {
            return Math.max(0, (24 - currentHour) + fundingHour - 1);
        }
        
        // 如果相差超过一天
        return Math.max(0, (24 - currentHour) + fundingHour + 23);
    } catch (e) {
        console.error('计算结算次数出错:', e);
        return 0;
    }
}

// 更新高费率代币表格
function updateHighRateTokensTable(allContracts) {
    console.log("开始更新高费率代币表格，数据:", allContracts);
    const tbody = document.getElementById('hlHighRateTokens');
    if (!tbody) {
        console.error('找不到表格元素');
        return;
    }

    // 将对象转换为数组并过滤掉无效数据
    const tokens = Object.entries(allContracts)
        .map(([symbol, contract]) => {
            if (!contract) {
                return null;
            }
            
            // 只处理 Hyperliquid 上有效费率的代币
            if (contract.hl_rate === null || contract.hl_rate === undefined || Math.abs(contract.hl_rate) === 0) {
                return null;
            }
            
            // Hyperliquid费率需要乘以100
            const hlRate = contract.hl_rate * 100;
            const bnRate = contract.binance_rate;
            
            // 计算费率差（绝对值）
            const difference = (hlRate !== null && bnRate !== null) ? Math.abs(hlRate - bnRate) : null;

            // 处理结算时间
            const binanceNextFunding = contract.binance_next_funding && contract.binance_next_funding !== '-' ? 
                contract.binance_next_funding : null;
            const hlNextFunding = contract.hl_next_funding && contract.hl_next_funding !== '-' ? 
                contract.hl_next_funding : null;
            
            return {
                symbol,
                hl_rate: hlRate,
                binance_rate: bnRate,
                difference: difference,
                binance_next_funding: binanceNextFunding,
                next_funding_hl: hlNextFunding,
                has_valid_funding: binanceNextFunding !== null // 标记是否有有效的结算时间
            };
        })
        .filter(token => token !== null);

    console.log("处理后的代币数据:", tokens);

    if (tokens.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center">暂无数据</td></tr>';
        return;
    }

    // 首先按是否有有效结算时间排序，然后按Hyperliquid费率绝对值从大到小排序
    tokens.sort((a, b) => {
        if (a.has_valid_funding !== b.has_valid_funding) {
            return b.has_valid_funding ? 1 : -1;
        }
        return Math.abs(b.hl_rate) - Math.abs(a.hl_rate);
    });

    // 只取前20个
    const top20Tokens = tokens.slice(0, 20);

    // 生成表格内容
    const html = top20Tokens.map((token, index) => {
        // 计算结算次数
        const settlementCount = calculateSettlementCount(token.binance_next_funding);

        // 计算结算费率
        const settlementRate = Math.abs(token.hl_rate) * settlementCount;
        const isProfitable = settlementRate >= 0.25; // 0.25%

        return `
            <tr>
                <td>${index + 1}</td>
                <td>${token.symbol}</td>
                <td class="${getColorClass(token.hl_rate)}">${formatRate(token.hl_rate, 4, true)}</td>
                <td class="${getColorClass(token.binance_rate)}">${formatRate(token.binance_rate, 4, true)}</td>
                <td>${formatRate(token.difference, 4, false)}</td>
                <td>${formatDateTime(token.binance_next_funding)}</td>
                <td>${formatDateTime(token.next_funding_hl)}</td>
                <td>${settlementCount}</td>
                <td class="${isProfitable ? 'text-danger' : ''}">${formatRate(settlementRate, 4, false)}</td>
            </tr>
        `;
    }).join('');

    tbody.innerHTML = html;
}

// 获取交易对的最大杠杆倍数
async function getMaxLeverage(exchange, symbol) {
    try {
        let response;
        let processedSymbol;
        
        if (exchange === 'binance') {
            // 对于币安，确保使用USDT后缀
            processedSymbol = symbol.endsWith('USDT') ? symbol : `${symbol}USDT`;
        } else {
            // 对于Hyperliquid，只使用基础货币名称（如从BTC/USDC:USDC中提取BTC）
            processedSymbol = symbol.split('/')[0];
        }
        
        console.log(`获取${exchange}交易所${processedSymbol}的最大杠杆`);
        response = await fetch(`/api/${exchange}/max_leverage/${processedSymbol}`);
        
        const result = await response.json();
        if (result.status === 'success') {
            console.log(`${exchange}交易所${processedSymbol}的最大杠杆为: ${result.data}`);
            return result.data;
        }
        console.log(`获取${exchange}交易所${processedSymbol}的最大杠杆失败，使用默认值1`);
        return 1; // 默认返回1倍杠杆
    } catch (error) {
        console.error(`获取${exchange}交易所${symbol}最大杠杆倍数失败:`, error);
        return 1;
    }
}

// 更新自动交易配置区
async function updateAutoTradeConfig(opportunities) {
    const tbody = document.getElementById('currentOpportunityBody');
    if (!tbody) return;
    
    // 清空现有内容
    tbody.innerHTML = '';
    
    // 获取两个交易所的余额
    const [binanceBalanceResponse, hlBalanceResponse] = await Promise.all([
        fetch('/api/binance/balance').then(response => response.json()),
        fetch('/api/hyperliquid/balance').then(response => response.json())
    ]);
    
    // 获取仓位比例，添加默认值
    const positionRatioElement = document.getElementById('positionRatioInput');
    const positionRatio = positionRatioElement ? parseFloat(positionRatioElement.value) : 0.5;
    
    // 遍历所有有套利策略的机会
    for (const opp of opportunities) {
        if (opp.strategy && opp.strategy !== '暂无策略') {
            const strategy = opp.strategy.toLowerCase();
            let longExchange, shortExchange, longRate, shortRate;

            // 根据策略设置交易所和费率
            if (strategy.includes('hyperliquid做多')) {
                longExchange = 'hyperliquid';
                shortExchange = 'binance';
                longRate = opp.hl_rate;
                shortRate = opp.binance_rate;
            } else if (strategy.includes('hyperliquid做空')) {
                longExchange = 'binance';
                shortExchange = 'hyperliquid';
                longRate = opp.binance_rate;
                shortRate = opp.hl_rate;
            } else {
                continue; // 跳过没有明确策略的机会
            }
            
            // 获取两个交易所的最大杠杆倍数
            const [longMaxLeverage, shortMaxLeverage] = await Promise.all([
                getMaxLeverage(longExchange, opp.symbol),
                getMaxLeverage(shortExchange, opp.symbol)
            ]);
            
            // 取两个交易所最大杠杆的较小值
            const maxLeverage = Math.min(longMaxLeverage, shortMaxLeverage);
            
            // 计算建议仓位
            const binanceBalance = binanceBalanceResponse.status === 'success' ? binanceBalanceResponse.data.balance : 0;
            const hlBalance = hlBalanceResponse.status === 'success' ? hlBalanceResponse.data.balance : 0;
            
            // 计算两个交易所的建议仓位
            const binanceSuggestedPosition = binanceBalance * maxLeverage * positionRatio;
            const hlSuggestedPosition = hlBalance * maxLeverage * positionRatio;
            
            // 取较小值作为最终建议仓位
            const suggestedPosition = Math.min(binanceSuggestedPosition, hlSuggestedPosition);
            
            // 计算预计利润
            const totalFee = 0.002; // 总手续费率 0.2%
            const rateDifference = Math.abs(opp.difference) / 100; // 转换为小数
            const expectedProfit = suggestedPosition * (rateDifference - totalFee);
            
            // 创建表格行
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${opp.symbol}</td>
                <td>${longExchange === 'hyperliquid' ? 'Hyperliquid' : 'Binance'}</td>
                <td class="${getColorClass(longRate)}">${formatRate(longRate)}</td>
                <td>${shortExchange === 'hyperliquid' ? 'Hyperliquid' : 'Binance'}</td>
                <td class="${getColorClass(shortRate)}">${formatRate(shortRate)}</td>
                <td class="${getColorClass(opp.difference)}">${formatRate(opp.difference)}</td>
                <td>${formatDateTime(opp.binance_next_funding)}</td>
                <td>${formatDateTime(opp.next_funding_hl)}</td>
                <td>${suggestedPosition.toFixed(2)} USDT</td>
                <td>${maxLeverage}x</td>
                <td class="text-success">${(positionRatio * 100).toFixed(0)}%</td>
                <td class="${expectedProfit > 0 ? 'text-success' : 'text-danger'}">${expectedProfit.toFixed(2)} USDT</td>
                <td>
                    <button class="btn btn-sm btn-primary" onclick="executeArbitrage('${opp.symbol}')">
                        执行套利
                    </button>
                </td>
            `;
            
            tbody.appendChild(tr);
        }
    }
    
    // 如果没有套利机会，显示提示信息
    if (tbody.children.length === 0) {
        tbody.innerHTML = '<tr><td colspan="12" class="text-center">暂无套利机会</td></tr>';
    }
}

// 更新套利机会表格
function updateArbitrageTable(opportunities) {
    try {
        const arbitrageTable = document.getElementById('arbitrageOpportunities');
        if (!arbitrageTable) {
            console.error('找不到套利机会表格元素');
            return;
        }

        if (!Array.isArray(opportunities) || opportunities.length === 0) {
            arbitrageTable.innerHTML = '<tr><td colspan="8" class="text-center">暂无套利机会</td></tr>';
            return;
        }

        const tableContent = opportunities.map((opp, index) => {
            try {
                if (!opp || typeof opp !== 'object') {
                    console.warn(`无效的套利机会数据:`, opp);
                    return null;
                }

                const hlRate = formatRate(opp.hl_rate);
                const bnRate = formatRate(opp.binance_rate);
                const rateDiff = formatRate(opp.difference);
                const bnNextFunding = formatDateTime(opp.binance_next_funding);
                const hlNextFunding = formatDateTime(opp.next_funding_hl);

                return `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${opp.symbol || '-'}</td>
                        <td class="${getColorClass(opp.binance_rate)}">${bnRate}</td>
                        <td class="${getColorClass(opp.hl_rate)}">${hlRate}</td>
                        <td class="${getColorClass(opp.difference)}">${rateDiff}</td>
                        <td>${bnNextFunding}</td>
                        <td>${hlNextFunding}</td>
                        <td>${opp.strategy || '暂无策略'}</td>
                    </tr>
                `;
            } catch (e) {
                console.error(`处理套利机会数据时出错:`, e);
                return null;
            }
        })
        .filter(row => row !== null)
        .join('');

        arbitrageTable.innerHTML = tableContent || '<tr><td colspan="8" class="text-center">暂无套利机会</td></tr>';
        
        // 更新自动交易配置区
        updateAutoTradeConfig(opportunities);
        
    } catch (error) {
        console.error('更新套利机会表格失败:', error);
        const arbitrageTable = document.getElementById('arbitrageOpportunities');
        if (arbitrageTable) {
            arbitrageTable.innerHTML = '<tr><td colspan="8" class="text-center">处理数据时出错</td></tr>';
        }
    }
}

// 刷新持仓信息
async function refreshPositions() {
    try {
        // 获取币安持仓
        const bnResponse = await fetch('/api/binance/position/all');
        const bnData = await bnResponse.json();
        updateBinancePositions(bnData);

        // 获取Hyperliquid持仓
        const hlResponse = await fetch('/api/hyperliquid/position/all');
        const hlData = await hlResponse.json();
        updateHyperliquidPositions(hlData);
    } catch (error) {
        console.error('刷新持仓信息失败:', error);
    }
}

// 更新币安持仓显示
function updateBinancePositions(data) {
    const container = document.getElementById('binancePositions');
    if (!container) return;

    if (data.status === 'success' && data.data.length > 0) {
        const positionsHtml = data.data.map(pos => {
            const positionSize = parseFloat(pos.positionAmt);
            const side = positionSize > 0 ? '多仓' : '空仓';
            const sideClass = positionSize > 0 ? 'text-success' : 'text-danger';
            const pnl = parseFloat(pos.unrealizedProfit);

            return `
                <div class="position-item mb-2 p-2 border rounded">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong>${pos.symbol}</strong>
                        <span class="${pnl >= 0 ? 'text-success' : 'text-danger'}">${pnl.toFixed(2)} USDT</span>
                    </div>
                    <div class="d-flex justify-content-between mt-1">
                        <span class="${sideClass}">${side}: ${Math.abs(positionSize).toFixed(4)}</span>
                        <span>杠杆: ${pos.leverage}x</span>
                    </div>
                    <div class="d-flex justify-content-between mt-1 small">
                        <span>开仓价: ${parseFloat(pos.entryPrice).toFixed(4)}</span>
                        <span>标记价: ${parseFloat(pos.markPrice).toFixed(4)}</span>
                    </div>
                    <div class="d-flex justify-content-end mt-2">
                        <button class="btn btn-sm btn-danger" onclick="closePosition('binance', '${pos.symbol}', ${positionSize})">
                            平仓
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        container.innerHTML = positionsHtml;
    } else {
        container.innerHTML = '<div class="text-center text-muted p-3">暂无持仓</div>';
    }
}

// 更新Hyperliquid持仓显示
function updateHyperliquidPositions(data) {
    const container = document.getElementById('hyperliquidPositions');
    if (!container) return;

    if (data.status === 'success' && data.data.length > 0) {
        const positionsHtml = data.data.map(pos => {
            const positionSize = parseFloat(pos.positionAmt);
            const side = positionSize > 0 ? '多仓' : '空仓';
            const sideClass = positionSize > 0 ? 'text-success' : 'text-danger';
            const pnl = parseFloat(pos.unrealizedProfit);

            return `
                <div class="position-item mb-2 p-2 border rounded">
                    <div class="d-flex justify-content-between align-items-center">
                        <strong>${pos.symbol}</strong>
                        <span class="${pnl >= 0 ? 'text-success' : 'text-danger'}">${pnl.toFixed(2)} USDC</span>
                    </div>
                    <div class="d-flex justify-content-between mt-1">
                        <span class="${sideClass}">${side}: ${Math.abs(positionSize).toFixed(4)}</span>
                        <span>杠杆: ${pos.leverage}x</span>
                    </div>
                    <div class="d-flex justify-content-between mt-1 small">
                        <span>开仓价: ${parseFloat(pos.entryPrice).toFixed(4)}</span>
                        <span>标记价: ${parseFloat(pos.markPrice).toFixed(4)}</span>
                    </div>
                    <div class="d-flex justify-content-end mt-2">
                        <button class="btn btn-sm btn-danger" onclick="closePosition('hyperliquid', '${pos.symbol}', ${positionSize})">
                            平仓
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        container.innerHTML = positionsHtml;
    } else {
        container.innerHTML = '<div class="text-center text-muted p-3">暂无持仓</div>';
    }
}

// 获取手续费率
async function fetchCommissionRates() {
    try {
        // 获取币安手续费率
        const bnResponse = await fetch('/api/binance/commission_rate');
        const bnData = await bnResponse.json();
        if (bnData.status === 'success') {
            document.getElementById('binanceMakerFee').textContent = `${(bnData.data.maker * 100).toFixed(3)}%`;
            document.getElementById('binanceTakerFee').textContent = `${(bnData.data.taker * 100).toFixed(3)}%`;
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

// 处理交易对变化，更新杠杆倍数
async function handleSymbolChange() {
    const exchange = document.getElementById('orderExchange').value;
    const symbol = document.getElementById('orderSymbol').value;
    const leverageInput = document.getElementById('orderLeverage');
    
    if (!symbol) {
        return;
    }
    
    try {
        console.log(`获取${exchange}交易所${symbol}的最大杠杆`);
        let processedSymbol;
        
        if (exchange === 'binance') {
            processedSymbol = symbol.endsWith('USDT') ? symbol : `${symbol}USDT`;
        } else {
            processedSymbol = symbol.split('/')[0];
        }
        
        console.log(`处理后的交易对: ${processedSymbol}`);
        const response = await fetch(`/api/${exchange}/max_leverage/${processedSymbol}`);
        const result = await response.json();
        
        if (result.status === 'success') {
            const maxLeverage = result.data;
            console.log(`获取到最大杠杆: ${maxLeverage}`);
            
            // 设置输入框的最大值和默认值
            leverageInput.setAttribute('max', maxLeverage);
            leverageInput.value = '1';
            
            // 更新最大杠杆显示
            const maxLeverageDisplay = document.getElementById('maxLeverageDisplay');
            if (maxLeverageDisplay) {
                maxLeverageDisplay.textContent = `最大杠杆: ${maxLeverage}x`;
            }
        } else {
            console.error('获取杠杆倍数失败:', result.message);
            leverageInput.value = '1';
            leverageInput.setAttribute('max', '1');
        }
    } catch (error) {
        console.error('获取杠杆倍数失败:', error);
        leverageInput.value = '1';
        leverageInput.setAttribute('max', '1');
    }
}

// 处理杠杆输入
function handleLeverageInput(event) {
    const input = event.target;
    const maxLeverage = parseInt(input.getAttribute('max'));
    let value = parseInt(input.value);
    
    // 如果输入为空或非数字，设置为1
    if (isNaN(value) || value < 1) {
        value = 1;
    }
    // 如果超过最大杠杆，设置为最大杠杆
    else if (value > maxLeverage) {
        value = maxLeverage;
    }
    
    input.value = value;
}

// 处理交易所切换
async function handleExchangeChange() {
    const exchange = document.getElementById('orderExchange').value;
    const symbolSelect = document.getElementById('orderSymbol');
    const leverageInput = document.getElementById('orderLeverage');
    
    try {
        // 销毁现有的Select2实例
        if ($(symbolSelect).data('select2')) {
            $(symbolSelect).select2('destroy');
        }
        
        // 清空现有选项
        symbolSelect.innerHTML = '<option value="">选择或输入交易对</option>';
        
        // 获取交易对列表
        const response = await fetch(`/api/${exchange}/symbols`);
        const result = await response.json();
        
        if (result.status === 'success') {
            const symbols = result.data;
            const options = symbols.map(symbolInfo => {
                let value, text;
                if (exchange === 'binance') {
                    value = symbolInfo.symbol;
                    text = value;
                } else {
                    const baseAsset = symbolInfo.baseAsset;
                    value = `${baseAsset}/USDC:USDC`;
                    text = value;
                }
                return new Option(text, value, false, false);
            });
            
            // 添加选项到select元素
            options.forEach(option => symbolSelect.appendChild(option));
            
            // 初始化Select2
            $(symbolSelect).select2({
                placeholder: '选择或输入交易对',
                allowClear: true,
                width: '100%',
                dropdownParent: $(symbolSelect).parent(),
                matcher: function(params, data) {
                    // 如果没有搜索词，返回所有选项
                    if ($.trim(params.term) === '') {
                        return data;
                    }

                    // 如果选项为空，返回null
                    if (typeof data.text === 'undefined') {
                        return null;
                    }

                    // 执行实际的搜索匹配
                    if (data.text.toLowerCase().indexOf(params.term.toLowerCase()) > -1) {
                        return data;
                    }

                    return null;
                }
            }).on('select2:select', function(e) {
                // 确保选中的值被正确设置
                const selectedValue = e.params.data.id;
                $(this).val(selectedValue).trigger('change');
                handleSymbolChange();
            });
            
            // 重置杠杆输入框
            leverageInput.value = '1';
            leverageInput.setAttribute('max', '1');
            
            // 重置最大杠杆显示
            const maxLeverageDisplay = document.getElementById('maxLeverageDisplay');
            if (maxLeverageDisplay) {
                maxLeverageDisplay.textContent = '最大杠杆: 1x';
            }
        }
    } catch (error) {
        console.error('获取交易对列表失败:', error);
    }
}

// 刷新交易对列表
async function refreshSymbols() {
    await handleExchangeChange();
}

// 提交订单
async function submitOrder(event) {
    event.preventDefault();
    
    const submitButton = document.getElementById('submitOrderBtn');
    submitButton.disabled = true;
    
    try {
        const exchange = document.getElementById('orderExchange').value;
        let symbol = document.getElementById('orderSymbol').value;
        const side = document.getElementById('orderSide').value;
        const leverage = parseInt(document.getElementById('orderLeverage').value);
        const orderType = document.getElementById('orderType').value;
        const amount = parseFloat(document.getElementById('orderAmount').value);
        const price = orderType === 'LIMIT' ? parseFloat(document.getElementById('orderPrice').value) : null;
        
        // 根据交易所处理交易对格式
        if (exchange === 'binance' && !symbol.endsWith('USDT')) {
            symbol = symbol + 'USDT';
        } else if (exchange === 'hyperliquid' && !symbol.includes('/USDC:USDC')) {
            // 如果是Hyperliquid但不是完整格式，添加后缀
            symbol = `${symbol}/USDC:USDC`;
        }
        
        const orderData = {
            symbol: symbol,
            side: side,
            quantity: amount,
            leverage: leverage,
            order_type: orderType,
            price: price
        };
        
        console.log('提交订单数据:', orderData);
        
        const response = await fetch(`/api/${exchange}/order`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(orderData)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            alert('下单成功！');
            // 刷新持仓信息
            await refreshPositions();
        } else {
            alert('下单失败：' + result.message);
        }
    } catch (error) {
        console.error('下单失败:', error);
        alert('下单失败：' + error.message);
    } finally {
        submitButton.disabled = false;
    }
}

// 平仓功能
async function closePosition(exchange, symbol, positionSize) {
    try {
        // 处理交易对格式
        let processedSymbol;
        if (exchange === 'binance') {
            processedSymbol = symbol.endsWith('USDT') ? symbol : symbol + 'USDT';
        } else {
            // 对于Hyperliquid，我们需要移除/USDC:USDC后缀
            processedSymbol = symbol.includes('/USDC:USDC') ? 
                symbol.replace('/USDC:USDC', '') : symbol;
        }
        
        console.log(`正在平仓: ${exchange} ${symbol}, 处理后的交易对: ${processedSymbol}`);
        
        // 使用正确的API路径
        const apiPath = `${exchange === 'binance' ? 
            `/api/binance/position/${processedSymbol}/close` : 
            `/api/hyperliquid/position/${processedSymbol}/close`}`;
        
        const response = await fetch(apiPath, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        if (result.status === 'success') {
            alert('平仓成功！');
            await refreshPositions(); // 刷新持仓信息
        } else {
            alert('平仓失败：' + result.message);
        }
    } catch (error) {
        console.error('平仓失败:', error);
        alert('平仓失败：' + error.message);
    }
}

// 一键平仓所有持仓
async function closeAllPositions() {
    if (!confirm('确定要平掉所有持仓吗？')) {
        return;
    }
    
    try {
        const promises = [];
        
        // 获取当前持仓
        const [bnPositionsResponse, hlPositionsResponse] = await Promise.all([
            fetch('/api/binance/position/all'),
            fetch('/api/hyperliquid/position/all')
        ]);
        
        const [bnPositions, hlPositions] = await Promise.all([
            bnPositionsResponse.json(),
            hlPositionsResponse.json()
        ]);
        
        // 处理币安持仓
        if (bnPositions.status === 'success' && bnPositions.data.length > 0) {
            bnPositions.data.forEach(pos => {
                if (parseFloat(pos.positionAmt) !== 0) {
                    promises.push(closePosition('binance', pos.symbol, parseFloat(pos.positionAmt)));
                }
            });
        }
        
        // 处理Hyperliquid持仓
        if (hlPositions.status === 'success' && hlPositions.data.length > 0) {
            hlPositions.data.forEach(pos => {
                if (parseFloat(pos.positionAmt) !== 0) {
                    promises.push(closePosition('hyperliquid', pos.symbol, parseFloat(pos.positionAmt)));
                }
            });
        }
        
        // 等待所有平仓操作完成
        await Promise.all(promises);
        
        alert('所有持仓已平仓成功！');
        await refreshPositions(); // 刷新持仓信息
    } catch (error) {
        console.error('一键平仓失败:', error);
        alert('一键平仓失败：' + error.message);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', async function() {
    console.log('页面开始初始化...');
    
    try {
        // 添加杠杆输入事件监听
        const leverageInput = document.getElementById('orderLeverage');
        if (leverageInput) {
            leverageInput.addEventListener('input', handleLeverageInput);
            leverageInput.addEventListener('change', handleLeverageInput);
        }
        
        // 首先加载交易对列表
        await handleExchangeChange();
        
        // 初始化各个功能区域
        await Promise.all([
            refreshBalances(),
            refreshPositions(),
            fetchCommissionRates(),
            refreshFundingRates()
        ]);
        
        // 设置定时刷新
        setInterval(refreshFundingRates, 30000);  // 每30秒刷新一次资金费率
        setInterval(async () => {
            await Promise.all([
                refreshBalances(),
                refreshPositions()
            ]);
        }, 30000);  // 每30秒刷新一次余额和持仓
        
        // 在页面加载完成后添加一键平仓按钮的事件监听
        const closeAllPositionsBtn = document.getElementById('closeAllPositionsBtn');
        if (closeAllPositionsBtn) {
            closeAllPositionsBtn.addEventListener('click', closeAllPositions);
        }
        
        console.log('初始化完成');
    } catch (error) {
        console.error('初始化失败:', error);
    }
}); 