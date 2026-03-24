from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return '你好，笔记系统！'

if __name__ == '__main__':
    app.run(debug=True)