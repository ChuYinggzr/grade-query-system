# SQLAlchemy 写法说明：按已学过的 Flask 代码理解

本次不改成 Flask 接口：菜单调用业务函数，业务函数通过 SQLAlchemy 操作 MySQL。

## 1. 配置和会话

~~~python
load_dotenv(Path(__file__).with_name(".env"))
~~~

Path(__file__) 表示当前代码文件路径；with_name(".env") 指向同目录的配置文件；load_dotenv() 把配置加载到环境变量，os.getenv() 再读取配置值。

~~~python
database_url = URL.create(
    "mysql+pymysql",
    username=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "grade_system"),
    query={"charset": "utf8mb4"},
)
engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
~~~

- URL.create() 生成连接配置；mysql+pymysql 表示数据库是 MySQL，驱动是 PyMySQL。密码中的特殊字符不用手动编码。
- create_engine() 创建数据库引擎，管理连接池；不是这行就立刻建表或写数据。
- pool_pre_ping=True 在取出池中连接时检查连接可用性，不是所有数据库错误都能自动修好。
- sessionmaker(bind=engine) 创建会话工厂，SessionLocal() 才会生成一次操作使用的会话。
- 会话用来查询、跟踪模型对象的修改，以及提交或回滚；这里对应 Flask 中 db.session 的用途。

~~~python
with SessionLocal() as db_session:
    # 在这里进行一次查询或增删改。
    ...
~~~

with 离开时关闭会话、释放占用的连接资源。未提交的事务不会因此自动保存。与 Flask 应用上下文不同，这里不需要启动 Web 服务器。

## 2. 模型

~~~python
Base = declarative_base()

class Student(Base):
    __tablename__ = "student"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    class_name = Column(String(50))
~~~

- Base 是模型共用的基类，作用对应 Flask-SQLAlchemy 已提供的 db.Model；这是非 Flask 项目需要自己准备的部分。
- Student 是 Python 类，student 是数据库表名，两者不必相同。
- Column 声明字段；Integer 对应整数，String(50) 对应 VARCHAR(50)。
- primary_key=True 表示主键，autoincrement=True 表示自增，nullable=False 表示不允许 NULL。
- 定义类只是描述表结构，并不自动创建数据库或表。
- 本项目显式执行 python mysql.py --init-db 时才调用 Base.metadata.create_all(engine)，创建缺少的表；它不是数据库迁移工具。

Score 模型中的：

~~~python
ForeignKey("student.id", name="fk_score_student", ondelete="CASCADE")
UniqueConstraint("student_id", "course_id", name="uk_student_course")
score = Column(Numeric(5, 2), nullable=False)
~~~

分别对应原来的外键、学生和课程的联合唯一约束、DECIMAL(5,2) 分数字段。删除学生时删除相关成绩依靠数据库的外键级联，不是 Python 的 relationship。已有表要原本就有正确外键，create_all() 不会补改已有表。

## 3. 新增：与你写过的 User(...) + add() + commit() 一样

~~~python
student = Student(name=name, class_name=class_name)
db_session.add(student)
db_session.commit()
return student.id
~~~

1. Student(...) 创建一个表示新学生的 Python 对象，此时没有保存到数据库。
2. add(student) 将对象加入会话，准备插入。
3. commit() 刷新并提交事务，成功后数据库中才有已提交的记录。
4. student.id 是数据库生成的主键，函数返回它，菜单可以显示学号。

add_course()、add_score() 使用同样逻辑，只是模型和字段不同。

## 4. 查询

~~~python
student = db_session.get(Student, student_id)
~~~

get() 根据主键查找一名学生，返回模型对象；不存在则返回 None。它不能在第二个参数中直接按姓名查询。

~~~python
record = db_session.query(Score).filter_by(
    student_id=student_id,
    course_id=course_id,
).first()
~~~

query(Score) 表示查询成绩模型；filter_by() 按两个字段筛选（相当于 AND）；first() 取得第一条符合条件的记录，没有则返回 None。由于联合唯一约束，同一学生同一课程最多一条。

query() 是旧式但仍被 SQLAlchemy 2.0 支持的接口，本项目保留这种更接近已有 Flask 练习的写法，不表示它是新项目唯一的查询方式。

## 5. 修改：修改查出来的对象

~~~python
record = find_score(db_session, student_id, course_id)
if record is None:
    return False
record.score = new_score
db_session.commit()
return True
~~~

find_score() 是本文件已经定义的辅助函数。查不到就返回 False；查到后修改 record.score，commit() 将属性修改写回数据库。这里不能重新创建一个 Score(...) 代替修改，否则不是更新原记录。

## 6. 删除

~~~python
student = db_session.get(Student, student_id)
if student is None:
    return False
db_session.delete(student)
db_session.commit()
return True
~~~

先查到要删除的对象，delete() 标记删除，commit() 提交。删除学生或课程会触发原来的外键级联；删除一条成绩不会删除它关联的学生或课程。

## 7. 多表查询继续写 SQL

~~~python
rows = db_session.execute(
    text("""
        SELECT s.name, c.name, sc.score
        FROM score sc
        JOIN student s ON sc.student_id = s.id
        JOIN course c ON sc.course_id = c.id
        WHERE sc.student_id = :student_id
        ORDER BY c.id
    """),
    {"student_id": student_id},
).all()
~~~

- SQL 中的 JOIN 和 WHERE 仍是你学过的 MySQL 逻辑。
- text() 把字符串声明为 SQLAlchemy 可以执行的文本 SQL。
- :student_id 是值的占位符，不是拼接用户输入；参数字典提供实际值。
- PyMySQL 游标用的 %s，改成 SQLAlchemy 文本 SQL 后使用 :参数名。
- execute() 执行语句；all() 收集结果行，没记录就是 []。
- 这里返回的是 Row 结果行，不是 Student 对象，也不是自动变成字典。

~~~python
for name, course, score in rows:
    print(f"{name} | {course} | {score}")
~~~

每行恰好有三个查询字段，依次解包到三个变量，再显示给命令行用户。此处不是 JSON API，因此不需要 jsonify()。

## 8. 异常处理

~~~python
try:
    db_session.add(record)
    db_session.commit()
except IntegrityError:
    db_session.rollback()
    print("录入失败：成绩重复，或学生、课程已被删除")
except SQLAlchemyError:
    db_session.rollback()
    print("录入失败：请检查数据库连接、表结构和权限")
~~~

IntegrityError 是约束错误，不是只代表“重复”；SQLAlchemyError 处理其他 SQLAlchemy 数据库异常。先捕获更具体的异常，再捕获更广的异常。

rollback() 回滚未提交修改，并恢复当前会话可继续使用的状态；它不会把错误的数据自动修好。查询后的重复检查不能阻止其他进程同时插入，所以仍需数据库唯一约束和提交时异常处理。

程序不把原始异常中的 SQL、参数等信息直接输出给普通使用者，避免泄露连接和业务信息。故障提示需要配合检查配置、服务和权限，不能把所有失败都当成重复。

## 9. 本次改造和保持不变的内容

- 保持三张表、原菜单编号、主要业务功能、多表 SQL 查询和外键级联。
- 增删改由游标执行 SQL 改为操作模型对象；每次操作显式提交或回滚。
- 补充 .env 加载及安全模板、依赖安装说明和自动测试。
- 新增操作显示生成的学号、课程号，便于后续录入。
- 分数输入先保留为文本，再转 Decimal；拒绝无穷大、NaN、越界及超过两位有效小数。
- 增加不会清库的 --init-db；保留原 schema.sql 作为历史示例，但该脚本会清库，已有数据时不要执行。
- 测试和文档由 AI 辅助编写，改造代码也由 AI 辅助实现，需要本人理解后再用于项目介绍。

参考：[SQLAlchemy 会话官方说明](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)、[声明式模型官方说明](https://docs.sqlalchemy.org/en/20/orm/declarative_styles.html)。
