import sqlite3
from binance.spot import Spot



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

# 创建订单表（增加 effective 字段）
cursor.execute('''
CREATE TABLE IF NOT EXISTS orders
(orderId TEXT PRIMARY KEY, symbol TEXT, side TEXT, price REAL, quantity REAL, status TEXT, effective INTEGER)
''')
conn.commit()

def print_orders(orders):
    #count_valid_orders = sum(1 for order in orders if order['status'] == 'NEW')
    #print(f"有效订单数量: {count_valid_orders}")

    # 筛选并打印当前有效的订单
    for order in orders:
        if order['status'] == 'NEW':  # 'NEW' 状态表示订单仍然有效
            print(f"订单ID: {order['orderId']}")
            print(f"交易对: {order['symbol']}")
            print(f"订单类型: {order['type']}")
            print(f"方向: {order['side']}")
            print(f"价格: {order['price']}")
            print(f"数量: {order['origQty']}")
            print(f"TimeInForce: {order['timeInForce']}")
            print("------------------------")

def get_active_orders(symbol):
    active_orders = client.get_open_orders(symbol)
    return {order['orderId']: order for order in active_orders if order['status'] == 'NEW'}

def save_orders_to_db(orders):
    for order in orders.values():
        cursor.execute('''
        INSERT OR REPLACE INTO orders (orderId, symbol, side, price, quantity, status, effective)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (order['orderId'], order['symbol'], order['side'], float(order['price']), float(order['origQty']), order['status'], 1))
    conn.commit()

def get_db_orders(symbol):
    cursor.execute('SELECT orderId, symbol, side, price, quantity, status FROM orders WHERE status = "NEW" AND effective = 1 AND symbol = ?', (symbol,))
    return {row[0]: {'orderId': row[0], 'symbol': row[1], 'side': row[2], 'price': row[3], 'quantity': row[4], 'status': row[5]} for row in cursor.fetchall()}

def place_new_order(symbol, side, price, quantity):
    try:
        new_order = client.new_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            timeInForce='GTC',
            quantity=quantity,
            price=price
        )
        print(f"新订单已下: {new_order}")
        return new_order
    except Exception as e:
        print(f"下单失败: {e}")
        return None

def initialize_db():
    active_orders = get_active_orders()
    save_orders_to_db(active_orders)
    print(f"初始化数据库完成,保存了 {len(active_orders)} 个活跃订单")

def main():
    symbol = "FETUSDT"
    cursor.execute('SELECT COUNT(*) FROM orders WHERE symbol = ?', (symbol,))
    if cursor.fetchone()[0] == 0:
        print("数据库为空,正在初始化...")
        initialize_db()
    
    while True:
        active_orders = get_active_orders(symbol)
        print("当前活跃订单:")
        print_orders(active_orders)
        db_orders = get_db_orders(symbol)
        print("数据库中订单:")
        print_orders(db_orders)
        # 检查是否有订单成交
        for order_id in db_orders:
            if order_id not in active_orders:
                completed_order = db_orders[order_id]
                print(f"订单已成交: {completed_order}")
                
                # 更新数据库中的订单状态和 effective 字段
                cursor.execute('UPDATE orders SET status = "FILLED", effective = 0 WHERE orderId = ?', (order_id,))
                conn.commit()
                
                # 下新订单
                symbol = completed_order['symbol']
                quantity = completed_order['quantity']
                if completed_order['side'] == 'BUY':
                    new_price = completed_order['price'] + 0.1
                    new_side = 'SELL'
                else:
                    new_price = completed_order['price'] - 0.1
                    new_side = 'BUY'
                
                new_order = place_new_order(symbol, new_side, new_price, quantity)
                if new_order:
                    save_orders_to_db({new_order['orderId']: new_order})
        
        # 保存当前活跃订单到数据库
        save_orders_to_db(active_orders)
        

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("程序已停止")
    finally:
        conn.close()
