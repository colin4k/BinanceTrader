import sqlite3
from binance.spot import Spot
import configparser
import datetime  # 添加此导入
import math

# 连接到SQLite数据库
import configparser

# 读取配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 初始化 Binance Spot 客户端
# 从配置文件中获取API密钥和密码
api_key = config['Binance']['api_key']
api_secret = config['Binance']['api_secret']
client = Spot(api_key=api_key, api_secret=api_secret)

# 从配置文件中获取数据库文件的绝对路径
db_path = config['Database']['path']

# 连接到SQLite数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders
    (orderId TEXT PRIMARY KEY, symbol TEXT, side TEXT, price REAL, quantity REAL, status TEXT, effection INTEGER,
    createTime TIMESTAMP, updateTime TIMESTAMP)
    ''')
conn.commit()

def print_orders(orders):
    #count_valid_orders = sum(1 for order in orders if order['status'] == 'NEW')
    #print(f"有效订单数量: {count_valid_orders}")

    # 筛选并打印当前有效的订单
    for order in orders:
        print(order)
def get_active_orders(symbol):
    active_orders = client.get_open_orders(symbol)
    #return {order['orderId']: order for order in active_orders if order['status'] == 'NEW'}
    return active_orders

def save_orders_to_db(orders):
    current_time = datetime.datetime.now()
    for order in orders:
        cursor.execute('''
        INSERT OR REPLACE INTO orders 
        (orderId, symbol, side, price, quantity, status, effection, createTime, updateTime)
        VALUES (?, ?, ?, ?, ?, ?, ?,?,?)
        ''', (order['orderId'], order['symbol'], order['side'], float(order['price']), 
              float(order['origQty']), order['status'], 1,current_time, current_time))
    conn.commit()

def get_db_orders(symbol):
    cursor.execute('SELECT orderId, symbol, side, price, quantity, status FROM orders WHERE status = "NEW" AND effection = 1 AND symbol = ?', (symbol,))
    return {row[0]: {'orderId': row[0], 'symbol': row[1], 'side': row[2], 'price': row[3], 'quantity': row[4], 'status': row[5]} for row in cursor.fetchall()}

def place_new_order(symbol, side, price, quantity):
    try:
        symbol_info = get_symbol_info(client, symbol)
        if not symbol_info:
            raise ValueError(f"无法获取 {symbol} 的信息")

        filters = {f['filterType']: f for f in symbol_info['filters']}
        price_filter = filters['PRICE_FILTER']
        tick_size = float(price_filter['tickSize'])

        rounded_price = round_price(price, tick_size)

        new_order = client.new_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            timeInForce='GTC',
            quantity=quantity,
            price=f"{rounded_price:.8f}".rstrip('0').rstrip('.')
        )
        print(f"新订单已下: {new_order}")
        return new_order
    except Exception as e:
        print(f"下单失败: {e}")
        return None

def get_symbol_info(client, symbol):
    exchange_info = client.exchange_info()
    for s in exchange_info['symbols']:
        if s['symbol'] == symbol:
            return s
    return None

def round_price(price, tick_size):
    return math.floor(price / tick_size) * tick_size

def initialize_db(symbol):
    # 创建订单表（增加 createTime 和 updateTime 字段）
    
    active_orders = get_active_orders(symbol)
    save_orders_to_db(active_orders)
    print(f"初始化数据库完成,保存了 {len(active_orders)} 个活跃订单")
    
def print_db_orders(db_orders):
    for order_id, order_info in db_orders.items():
        print(order_info)
        
def order_exists_in_active_orders(order_id, active_orders):
    return any(str(active_order['orderId']) == str(order_id) for active_order in active_orders)

def main():
    symbol = "FETUSDT"
    cursor.execute('SELECT COUNT(*) FROM orders WHERE symbol = ?', (symbol,))
    if cursor.fetchone()[0] == 0:
        print("数据库为空,正在初始化...")
        initialize_db(symbol)
    active_orders = get_active_orders(symbol)
    #print("当前活跃订单:")
    #print_orders(active_orders)
    db_orders = get_db_orders(symbol)
    #print("数据库中订单:")
    #print_db_orders(db_orders)
    # 检查是否有订单成交
    for order_id, db_order in db_orders.items():
        #print(db_order)
        if not order_exists_in_active_orders(db_order['orderId'], active_orders):
            # 处理不再活跃的订单
            print(f"订单 {db_order['orderId']} 不再活跃")
            # 这里添加处理不再活跃订单的逻辑
            # 更新数据库中的订单状态和 effection 字段
            current_time = datetime.datetime.now()
            cursor.execute('UPDATE orders SET effection = 0, updateTime = ? WHERE orderId = ?', (current_time, order_id))
            conn.commit()
            
            # 下新订单
            symbol = db_order['symbol']
            quantity = db_order['quantity']
            if db_order['side'] == 'BUY':
                new_price = float(db_order['price']) + 0.1
                new_side = 'SELL'
            else:
                new_price = float(db_order['price']) - 0.1
                new_side = 'BUY'
            
            new_order = place_new_order(symbol, new_side, new_price, quantity)
            if new_order:
                save_orders_to_db([new_order])  # 注意这里的修改
            
        else:
            print(f"订单 {db_order['orderId']} 仍然活跃")
            
            
    
    # 保存当前活跃订单到数据库
    save_orders_to_db(active_orders)
        

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("程序已停止")
    finally:
        conn.close()
