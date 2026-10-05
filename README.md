# 成绩管理系统

这是一个使用 Python、MySQL 和 Flask-SQLAlchemy 编写的命令行成绩管理练习项目。项目没有网页和接口，Flask 主要负责数据库配置与应用上下文，数据库代码使用 `db.Model`、`Model.query` 和 `db.session` 等常见写法。

## 功能

- 添加学生和课程。
- 录入、修改和删除成绩。
- 按学生、课程或全部记录查询成绩。
- 检查空值、字符长度、成绩范围和重复成绩。
- 删除学生或课程时，通过外键级联删除相关成绩。
- 数据库操作失败时执行回滚并显示错误提示。

## 熟悉的数据库写法

项目主要使用以下 Flask-SQLAlchemy 写法：

```python
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

student = Student(name="张三", class_name="计算机2401")
db.session.add(student)
db.session.commit()

student = db.session.get(Student, student_id)
score = Score.query.filter_by(
    student_id=student_id,
    course_id=course_id,
).first()

db.session.delete(student)
db.session.commit()
```

多表查询保留容易理解的 MySQL `JOIN`，通过 `db.session.execute(text(...))` 执行。PyMySQL 是 SQLAlchemy 连接 MySQL 使用的底层驱动，代码不再直接使用 `pymysql.connect()` 和游标。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `mysql.py` | Flask 配置、数据模型、增删改查和命令行菜单 |
| `README.md` | 项目介绍、安装和运行说明 |
| `SQLAlchemy写法说明.md` | 按代码顺序解释 Flask-SQLAlchemy 写法 |
| `requirements.txt` | Python 依赖 |
| `.env.example` | 不包含真实密码的环境变量模板 |
| `test_mysql.py` | 使用 SQLite 内存数据库运行自动测试 |
| `schema.sql` | 原始建库和示例数据脚本，会清空同名数据库 |

## 安装与配置

在项目目录中执行：

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

打开 `.env`，填写自己的 MySQL 配置：

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=grade_system
```

`.env` 已加入 `.gitignore`，不要提交真实密码。

## 第一次运行

先在 MySQL 中创建数据库：

```sql
CREATE DATABASE IF NOT EXISTS grade_system DEFAULT CHARACTER SET utf8mb4;
```

再执行：

```powershell
python mysql.py --init-db
python mysql.py
```

`--init-db` 调用 `db.create_all()` 创建缺少的表，不删除已有数据，也不能自动修改已经存在的表结构。

如果原项目中的三张表已经存在并且结构正确，可以直接执行：

```powershell
python mysql.py
```

不要在已有数据的数据库中执行 `schema.sql`，因为它包含 `DROP DATABASE`，会清空整个 `grade_system` 数据库。

## 操作顺序示例

1. 输入 `1` 添加学生，并记住生成的学号。
2. 输入 `2` 添加课程，并记住生成的课程号。
3. 输入 `3` 录入成绩。
4. 输入 `4`、`5` 或 `6` 查询成绩。
5. 输入 `7` 修改成绩。
6. 输入 `10` 删除一条成绩，或输入 `8`、`9` 删除学生、课程。
7. 输入 `0` 退出程序。

## 为什么需要应用上下文

这是命令行程序，没有浏览器请求替程序自动建立 Flask 应用上下文。因此主入口使用：

```python
with app.app_context():
    menu()
```

进入上下文后，菜单中的 `db.session` 才知道应当使用哪个 Flask 应用和数据库配置。运行 `python mysql.py` 时程序已经自动处理，不需要手动再写一次。

## 自动测试

```powershell
python -m py_compile mysql.py test_mysql.py
python -m unittest -v test_mysql
```

测试使用临时 SQLite 内存数据库，不会连接或修改个人 MySQL。测试覆盖增删改查、输入校验、重复成绩、外键、级联删除、事务回滚、初始化和菜单退出。

## 项目边界

- 项目是命令行练习，不包含 Flask 路由、网页、登录或 REST API。
- 三张表、菜单、主要功能和查询逻辑来自原始成绩查询项目。
- Flask-SQLAlchemy 结构整理、自动测试和说明文档经过 AI 辅助；项目使用者应理解代码后再用于简历和面试说明。

更详细的解释见 [SQLAlchemy写法说明](SQLAlchemy写法说明.md)。
