# 跨交易所资金费率套利监控系统

这是一个用于监控和执行币安（Binance）和 Hyperliquid 之间资金费率套利的系统。

## 功能特点

- 实时监控两个交易所的资金费率
- 自动计算套利机会
- 支持一键开仓和平仓
- 显示实时账户余额和持仓信息
- 自动计算最优杠杆和建议仓位
- 支持自定义资金费率差阈值
- 支持自定义仓位比例

## 本地安装步骤

### 1. 安装基本依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 Hyperliquid SDK

```bash
# 克隆 Hyperliquid SDK
git clone https://github.com/hyperliquid-dex/hyperliquid-python-sdk.git

# 进入 SDK 目录
cd hyperliquid-python-sdk

# 安装 SDK
pip install -e .

# 返回项目根目录
cd ..
```

## 服务器部署指南

### 1. 环境准备

```bash
# 更新系统包
sudo apt-get update
sudo apt-get upgrade -y

# 安装必要的系统包
sudo apt-get install -y python3 python3-pip git screen

# 创建项目目录
mkdir -p ~/trading
cd ~/trading
```

### 2. 克隆项目

```bash
# 克隆主项目
git clone https://github.com/tianxingj2021/taoli_bn-hl.git
cd taoli_bn-hl

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate
```

### 3. 安装依赖

```bash
# 安装基本依赖
pip install -r requirements.txt

# 安装 Hyperliquid SDK
git clone https://github.com/hyperliquid-dex/hyperliquid-python-sdk.git
cd hyperliquid-python-sdk
pip install -e .
cd ..
```

### 4. 配置文件设置

```bash
# 复制配置文件模板
cp config.json.example config.json

# 编辑配置文件
nano config.json
```

### 5. 使用Screen运行服务

```bash
# 创建新的screen会话
screen -S trading

# 激活虚拟环境（如果已关闭）
source venv/bin/activate

# 运行服务
python app.py

# 分离screen会话（按Ctrl+A，然后按D）
```

### 6. Screen 会话管理命令

```bash
# 查看所有screen会话
screen -ls

# 重新连接到trading会话
screen -r trading

# 终止会话（在会话中执行）
exit
```

### 7. 设置开机自启（可选）

创建系统服务文件：
```bash
sudo nano /etc/systemd/system/trading.service
```

添加以下内容：
```ini
[Unit]
Description=Trading Bot Service
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/trading/taoli_bn-hl
Environment="PATH=/home/YOUR_USERNAME/trading/taoli_bn-hl/venv/bin"
ExecStart=/home/YOUR_USERNAME/trading/taoli_bn-hl/venv/bin/python app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
# 替换配置文件中的YOUR_USERNAME
sudo sed -i 's/YOUR_USERNAME/'"$USER"'/g' /etc/systemd/system/trading.service

# 启用并启动服务
sudo systemctl enable trading.service
sudo systemctl start trading.service

# 查看服务状态
sudo systemctl status trading.service
```

### 8. 查看日志

```bash
# 如果使用screen运行
screen -r trading

# 如果使用系统服务运行
sudo journalctl -u trading.service -f
```

## 配置说明

1. 复制 `config.json.example` 为 `config.json`
2. 在 `config.json` 中填入您的 API 密钥：
```json
{
    "binance": {
        "api_key": "您的币安API密钥",
        "api_secret": "您的币安API密钥",
        "testnet": true
    },
    "hyperliquid": {
        "api_key": "您的Hyperliquid API密钥",
        "api_secret": "您的Hyperliquid API密钥",
        "testnet": true
    }
}
```

## 注意事项

- 请确保在使用前完全理解资金费率套利的风险
- 建议先使用小额资金测试
- API 密钥请妥善保管，不要泄露给他人
- 建议先在测试网进行测试（testnet设置为true）
- 在正式环境使用时，请将config.json中的testnet设置为false
- 服务器部署时建议使用screen或系统服务来确保程序持续运行
- 定期检查日志确保系统正常运行
- 建议设置监控和告警机制

## 依赖库说明

- flask: Web应用框架
- requests: HTTP请求库
- python-binance: Binance API客户端
- websocket-client: WebSocket连接支持
- python-dotenv: 环境变量管理
- ccxt: 加密货币交易库
- pandas: 数据分析工具
- hyperliquid-python-sdk: Hyperliquid交易所SDK

## 免责声明

本项目仅供学习和研究使用，作者不对使用本系统造成的任何损失负责。在使用本系统进行实际交易前，请充分了解相关风险。

# 加密货币交易API配置

这个项目提供了连接Binance和Hyperliquid交易所API的配置示例。

## 配置说明

1. 复制`config.json.example`文件并重命名为`config.json`
2. 在`config.json`中填入您的API密钥信息：
   - Binance API密钥和密钥
   - Hyperliquid API密钥和密钥

## 安装依赖

```bash
pip install -r requirements.txt
```

## 安全提示

- 永远不要将您的实际API密钥提交到版本控制系统中
- 建议将`config.json`添加到`.gitignore`文件中
- 请妥善保管您的API密钥，不要泄露给他人

## 依赖库说明

- flask: Web应用框架
- requests: HTTP请求库
- python-binance: Binance API客户端
- websocket-client: WebSocket连接支持
- python-dotenv: 环境变量管理
- ccxt: 加密货币交易库
- pandas: 数据分析工具 