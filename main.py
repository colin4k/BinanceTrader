import sqlite3
from binance.spot import Spot
import configparser
import datetime  # 添加此导入
import math
from push import push_message
import configparser

# 在文件开头添加以下函数
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    return datetime.datetime.fromisoformat(s)

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
        push_message(title="新订单通知", content=f"新订单已下: {new_order}")
        return new_order
    except Exception as e:
        print(f"下单失败: {e}")
        push_message(title="下单失败", content=f"下单失败: {e}")
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

# 获取当前symbol的价格
def get_current_price(client,symbol):
    try:
        ticker = client.ticker_price(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        print(f"获取{symbol}价格时发生错误: {e}")
        return None

def check_order_status(client, symbol, order_id):
    try:
        order_info = client.get_order(symbol=symbol, orderId=order_id)
        return order_info['status']
    except Exception as e:
        print(f"获取订单状态时发生错误: {e}")
        return None

def check_and_save_new_orders(active_orders, db_orders):
    new_orders = []
    for active_order in active_orders:
        order_id = str(active_order['orderId'])
        if active_order['status'] == 'NEW' and not any(order_id == str(db_order['orderId']) for db_order in db_orders.values()):
            print(f"发现新的有效订单：{order_id}")
            new_orders.append(active_order)
    
    if new_orders:
        save_orders_to_db(new_orders)
        print(f"已添加 {len(new_orders)} 个新订单到数据库")
    #else:
    #    print("没有发现新的有效订单")

def main():
    symbol = config['Binance']['symbol']
    cursor.execute('SELECT COUNT(*) FROM orders WHERE symbol = ?', (symbol,))
    if cursor.fetchone()[0] == 0:
        print("数据库为空，正在初始化...")
        initialize_db(symbol)
    
    active_orders = get_active_orders(symbol)
    db_orders = get_db_orders(symbol)

    # 检查是否有订单成交
    for order_id, db_order in db_orders.items():
        if not order_exists_in_active_orders(db_order['orderId'], active_orders):
            # 通过API检查订单状态
            order_status = check_order_status(client, db_order['symbol'], db_order['orderId'])
            
            if order_status == 'FILLED':
                print(f"订单 {db_order['orderId']} 已成交")
                # 更新数据库中的订单状态和 effection 字段
                current_time = datetime.datetime.now()
                cursor.execute('UPDATE orders SET status = ?, effection = 0, updateTime = ? WHERE orderId = ?', 
                               ('FILLED', current_time, order_id))
                conn.commit()
                
                # 下新订单
                symbol = db_order['symbol']
                quantity = db_order['quantity']
                price_step = float(config['Binance']['price_step'])
                if db_order['side'] == 'BUY':
                    new_price = round(float(db_order['price']) + 10 * price_step, 2)
                    new_side = 'SELL'
                else:
                    new_price = round(float(db_order['price']) - 10 * price_step, 2)
                    new_side = 'BUY'
                
                new_order = place_new_order(symbol, new_side, new_price, quantity)
                if new_order:
                    save_orders_to_db([new_order])
            else:
                print(f"订单 {db_order['orderId']} 状态为 {order_status}，将其effection设置为0")
                # 更新数据库中的订单状态和 effection 字段
                current_time = datetime.datetime.now()
                cursor.execute('UPDATE orders SET status = ?, effection = 0, updateTime = ? WHERE orderId = ?', 
                               (order_status, current_time, order_id))
                conn.commit()

    # 检查并保存新的有效订单
    check_and_save_new_orders(active_orders, db_orders)

    current_price = get_current_price(client, symbol)
    if current_price:
        print(f"当前时间:{datetime.datetime.now()}, {symbol}的当前价格为: {current_price}")
    else:
        print(f"当前时间:{datetime.datetime.now()}, 无法获取{symbol}的当前价格")

if __name__ == "__main__":
    try:
        # 在主代码之前添加以下注册
        sqlite3.register_adapter(datetime.datetime, adapt_datetime)
        sqlite3.register_converter("timestamp", convert_datetime)

        # 读取配置文件
        config = configparser.ConfigParser()
        config.read('config.ini')

        # 初始化 Binance Spot 客户端
        # 从配置文件中获取API密钥和密
        api_key = config['Binance']['api_key']
        api_secret = config['Binance']['api_secret']
        client = Spot(api_key=api_key, api_secret=api_secret)

        # 从配置文件中获取数据库文件的绝对路径
        db_path = config['Database']['path']

        # 修改数据库连接代码
        conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders
            (orderId TEXT PRIMARY KEY, symbol TEXT, side TEXT, price REAL, quantity REAL, status TEXT, effection INTEGER,
            createTime TIMESTAMP, updateTime TIMESTAMP)
            ''')
        conn.commit()
        main()
    except KeyboardInterrupt:
        print("程序已停止")
    finally:
        conn.close()
