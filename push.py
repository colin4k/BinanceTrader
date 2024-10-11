import requests
import json
import configparser

def push_message(title, content, template="html", topic="", channel="wechat"):
    """
    使用PushPlus推送消息
    
    参数:
    title (str): 消息标题
    content (str): 消息内容
    template (str): 发送模板,默认为html
    topic (str): 群组编码,不填仅发送给自己
    channel (str): 发送渠道,默认为微信公众号
    
    返回:
    dict: API响应结果
    """
    url = "http://www.pushplus.plus/send"
    # 读取配置文件
    config = configparser.ConfigParser()
    config.read('config.ini')
    token = config['PushPlus']['token']
    data = {
        "token": token,
        "title": title,
        "content": content,
        "template": template,
        "topic": topic,
        "channel": channel
    }
    
    headers = {"Content-Type": "application/json"}
    
    response = requests.post(url, data=json.dumps(data), headers=headers)
    
    return response.json()

# 使用示例
if __name__ == "__main__":
    title = "测试标题"
    content = "这是一条测试消息"
    
    result = push_message(title, content)
    print(result)