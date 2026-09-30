# 成绩查询系统

Python + MySQL + SQLAlchemy 的命令行练习项目。保留原来的菜单和三张表，将直接调用 PyMySQL 游标的业务代码改为 SQLAlchemy。

- 新增、修改、删除使用 ORM 模型对象、会话、提交和回滚。
- 多表成绩查询保留熟悉的 JOIN SQL，通过 SQLAlchemy 的 execute(text(...), 参数字典) 执行。
- PyMySQL 仍作为 SQLAlchemy 连接 MySQL 的底层驱动，不再直接调用 pymysql.connect()、cursor()。
- 这不是 Flask Web 项目，没有浏览器页面、路由、登录或 REST API。

## 功能

- 添加学生和课程，检查姓名、课程名、班级的长度，班级为空时使用“未分班”。
- 录入成绩：学生和课程必须存在，分数在 0～100 之间，最多两位小数，同一学生同一课程不允许重复。
- 查询某学生、某课程或全部成绩，保留原来的 JOIN 和排序。
- 修改已有成绩；删除学生、课程或某条成绩。
- 删除学生或课程时，由数据库的 ON DELETE CASCADE 删除相关成绩。
- 每次操作使用独立会话；写入成功后提交，数据库异常时回滚并显示提示。

## 文件

| 文件 | 用途 |
| --- | --- |
| mysql.py | 配置、模型、数据库操作、菜单，业务代码仍放在一个文件中 |
| README.md | 安装、运行、验证说明 |
| SQLAlchemy写法说明.md | 与自己学过的 Flask 写法对照、代码解释 |
| requirements.txt | 安装所需依赖 |
| .env.example | 不含真实密码的配置模板 |
| test_mysql.py | 自动测试，不使用个人 MySQL 数据库 |
| schema.sql | 原来的建库及示例数据脚本，**会清空 grade_system 数据库** |

## 安装与运行（Windows PowerShell）

先在项目目录的终端中执行：

~~~powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
~~~

用 PyCharm 打开刚生成的 .env，修改为自己的配置：

~~~dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的MySQL密码
DB_NAME=grade_system
~~~

.env 是本地文件，被 .gitignore 排除，不要上传；.env.example 只能保留示例占位值。程序读取 mysql.py 同目录下的 .env，已有系统环境变量优先。

### 已有原项目数据库

原项目 student、course、score 三张表的字段和约束与模型对应，通常只需要：

~~~powershell
python mysql.py
~~~

不要执行 schema.sql：它会删除整个 grade_system 数据库。**改成 SQLAlchemy 不要求重建原来的表。** 如果本地表被自行修改过，先检查表结构和外键，不能靠 create_all() 修复。

### 第一次运行，没有数据库

1. 在 DataGrip、PyCharm Database 或 MySQL 客户端中执行下面的 SQL：

~~~sql
CREATE DATABASE IF NOT EXISTS grade_system DEFAULT CHARACTER SET utf8mb4;
~~~

如果 .env 的 DB_NAME 不是 grade_system，请创建对应名称的数据库。

2. 回到项目终端执行：

~~~powershell
python mysql.py --init-db
python mysql.py
~~~

--init-db 只创建缺少的表，不删除已有数据，也不会修改已有表结构或生成迁移文件。新建的表没有示例数据，用菜单添加即可。本项目没有引入 Flask-Migrate / Alembic。

### 操作示例

1. 输入 1，添加学生“张三”和班级“计算机2401”，记下显示的学号。
2. 输入 2，添加课程“Python程序设计”，记下显示的课程号。
3. 输入 3，输入刚才的学号、课程号和分数 88.5。
4. 输入 4、5、6，分别验证学生、课程和全部成绩查询。
5. 再输入 3，重复录入同一学生同一课程，应该提示使用修改功能。
6. 输入 7，把分数改成 92.25，再输入 6 检查结果。
7. 输入 10，删除这条成绩，再输入 6，应该没有这条记录。
8. 再录入成绩后，用 8 或 9 删除关联学生或课程，验证相应成绩同时删除。
9. 输入 0，退出。不存在的 ID、空姓名、越界分数和非数字输入应显示提示。

## 自动验证

~~~powershell
python -m unittest -v test_mysql
python -m py_compile mysql.py test_mysql.py
~~~

15 项测试覆盖正常增删改查、空值/长度/分数校验、重复成绩、缺少关联对象、数据库约束、级联删除、提交失败回滚、连接错误处理、重复初始化保留数据以及菜单退出。

测试使用 SQLite 临时内存数据库，并开启外键；同时编译检查 MySQL 建表语句。**这些测试不是实际 MySQL 联调证明**，实际 MySQL 连接、账户权限及本地已有表结构仍需按照上面的操作示例验证。测试不会执行 schema.sql，不连接个人 MySQL，也不修改原有成绩数据。

## 与 Flask 写法的关系

逻辑相同，具体对象名不同：

| Flask-SQLAlchemy 中的写法 | 这里的 SQLAlchemy 写法 |
| --- | --- |
| class User(db.Model) | class Student(Base) |
| db.Column(db.String(50)) | Column(String(50)) |
| db.session.add(user) | db_session.add(student) |
| db.session.get(User, id) | db_session.get(Student, id) |
| User.query.filter_by(...).first() | db_session.query(Student).filter_by(...).first() |
| user.username = 新名字 | record.score = 新分数 |
| db.session.commit() / rollback() | db_session.commit() / rollback() |
| db.session.delete(user) | db_session.delete(student) |

这里没有 Flask 负责会话管理，因此使用 with SessionLocal() as db_session 创建和关闭会话，不需要 app.app_context()。with 结束时会关闭会话，**不会替你提交**，写操作仍需显式 commit()。

query(...).filter_by(...).first() 是 SQLAlchemy 2.0 仍支持的旧式查询接口，本项目为了与已学写法接近而采用；没有强行引入 Mapped、mapped_column、relationship 等未掌握的写法。

详细解释见 [SQLAlchemy写法说明](SQLAlchemy写法说明.md)。

## AI 辅助范围与项目边界

原始版本是 Python + PyMySQL 的个人练习项目。本次 SQLAlchemy 改造由 AI 辅助实现，包含数据库配置、模型定义、会话替换、输入校验补充、说明文档和自动测试；不应将这次改造描述为完全独立编写。

功能目标、原有菜单和 SQL 查询来自原始项目。使用者应逐段理解改造代码，再在简历和面试中如实说明自己能够解释、修改和独立实现的部分。项目属于命令行练习，不宣称生产部署、高并发性能或真实用户规模。
