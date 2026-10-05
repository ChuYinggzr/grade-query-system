# Flask-SQLAlchemy 写法说明

这份说明按照 `mysql.py` 的代码顺序，解释成绩管理系统中使用的数据库写法。

## 1. 创建 Flask 应用和数据库对象

```python
app = Flask(__name__)
```

- `Flask(__name__)` 创建 Flask 应用对象。
- `__name__` 给 Flask 提供当前模块的位置线索。
- 本项目没有网页路由，Flask 主要负责数据库配置和应用上下文。

```python
app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
```

- `SQLALCHEMY_DATABASE_URI` 告诉程序连接哪一个数据库。
- `mysql+pymysql` 表示使用 MySQL，底层驱动是 PyMySQL。
- `SQLAlchemy(app)` 把数据库功能绑定给 Flask 应用，之后可以使用 `db.Model`、`db.Column` 和 `db.session`。
- 数据库地址来自 `.env`，避免把真实密码写进代码和 GitHub。

## 2. 定义数据表模型

```python
class Student(db.Model):
    __tablename__ = "student"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    class_name = db.Column(db.String(50))
```

- `Student` 是 Python 模型类。
- `db.Model` 表示这个类是 Flask-SQLAlchemy 模型。
- `__tablename__` 指定数据库中的表名为 `student`。
- `db.Column` 定义字段。
- `primary_key=True` 表示主键。
- `autoincrement=True` 表示自动增加编号。
- `nullable=False` 表示数据库不允许该字段为 `NULL`。

课程表 `Course` 使用相同写法。成绩表还包含外键：

```python
student_id = db.Column(
    db.Integer,
    db.ForeignKey("student.id", ondelete="CASCADE"),
    nullable=False,
)
```

- `student.id` 表示关联学生表的 `id` 字段。
- `ondelete="CASCADE"` 表示删除学生时，数据库同时删除该学生的成绩。
- 课程外键的作用相同。

```python
__table_args__ = (
    UniqueConstraint("student_id", "course_id", name="uk_student_course"),
)
```

这是联合唯一约束：同一名学生的同一门课程只能保存一条成绩。学生姓名和课程名称本身不要求唯一。

## 3. 创建表

```python
db.create_all()
```

它会创建当前模型中缺少的表，但有三个限制：

1. 不会删除已有数据。
2. 不会自动修改已经存在的表结构。
3. 不是数据库迁移工具。

因此程序只在执行 `python mysql.py --init-db` 时调用它，不会每次打开菜单都自动建表。

## 4. 根据主键查询

```python
def select_student_by_id(student_id):
    return db.session.get(Student, student_id)
```

- `Student` 表示要查询的模型。
- `student_id` 是主键值。
- 查到时返回一个 `Student` 对象，查不到时返回 `None`。

课程查询使用完全相同的写法：

```python
db.session.get(Course, course_id)
```

## 5. 根据普通字段查询

```python
def select_score(student_id, course_id):
    return Score.query.filter_by(
        student_id=student_id,
        course_id=course_id,
    ).first()
```

- `Score.query` 表示查询成绩表。
- `filter_by()` 按字段筛选，多项条件之间相当于 `AND`。
- `first()` 返回第一条符合条件的数据，没有时返回 `None`。
- 因为数据库有联合唯一约束，这里最多只能查到一条。

## 6. 新增数据

```python
student = Student(name=name, class_name=class_name)
db.session.add(student)
db.session.commit()
return student.id
```

执行顺序是：

1. `Student(...)` 创建一个学生对象。
2. `db.session.add(student)` 把对象加入数据库会话。
3. `db.session.commit()` 提交事务，数据才真正保存。
4. 提交后可以读取数据库生成的 `student.id`。

添加课程和成绩也是同样的步骤，只是使用的模型和字段不同。

## 7. 修改数据

```python
record = select_score(student_id, course_id)

if record is None:
    return False

record.score = new_score
db.session.commit()
```

修改时必须先查到原来的对象，然后给对象属性重新赋值，最后提交。这里不能新建一个 `Score(...)`，否则会变成插入新记录。

## 8. 删除数据

```python
student = select_student_by_id(student_id)

if student is None:
    return False

db.session.delete(student)
db.session.commit()
```

- 先查询要删除的对象。
- `db.session.delete(student)` 标记删除。
- `db.session.commit()` 提交后，数据库才真正删除。
- 删除学生或课程时，外键级联会删除相关成绩。
- 只删除成绩时，不会删除学生或课程。

## 9. 使用 JOIN 查询多个表

```python
result = db.session.execute(
    text(
        """
        SELECT s.name, c.name, sc.score
        FROM score AS sc
        JOIN student AS s ON sc.student_id = s.id
        JOIN course AS c ON sc.course_id = c.id
        WHERE sc.student_id = :student_id
        ORDER BY c.id
        """
    ),
    {"student_id": student_id},
)
rows = result.all()
```

- SQL 中的 `JOIN`、`WHERE` 和 `ORDER BY` 都是普通 MySQL 查询语法。
- `text()` 把 SQL 字符串交给 SQLAlchemy 执行。
- `:student_id` 是参数占位符。
- 参数字典提供真实值，避免把用户输入直接拼接进 SQL。
- `result.all()` 取得全部结果，没有数据时得到空列表 `[]`。

结果中的每一行包含姓名、课程名和成绩：

```python
for name, course, score in rows:
    print(f"{name} | {course} | {score}")
```

这是命令行输出，不是 Web 接口，所以不需要 `jsonify()`。

## 10. 提交失败时回滚

```python
try:
    db.session.add(record)
    db.session.commit()
except IntegrityError:
    db.session.rollback()
    return False
except SQLAlchemyError:
    db.session.rollback()
    return False
```

- `IntegrityError` 常见于唯一约束或外键约束失败。
- `SQLAlchemyError` 接收其他 SQLAlchemy 数据库错误。
- 数据库操作失败后调用 `rollback()`，撤销本次没有成功提交的修改，并让会话恢复到可以继续使用的状态。
- 先捕获具体异常，再捕获范围更大的异常。

## 11. 为什么命令行程序需要 app.app_context()

```python
if __name__ == "__main__":
    with app.app_context():
        menu()
```

Flask Web 接口收到请求时，会自动建立应用上下文。这个项目是命令行程序，没有 HTTP 请求，所以需要手动进入应用上下文。进入后，`db.session` 才知道应当使用哪个 Flask 应用和数据库配置。

直接执行 `python mysql.py` 时，主入口已经自动完成这一步。只有你在其他文件中直接调用数据库函数时，才需要自己写：

```python
from mysql import app, add_student

with app.app_context():
    add_student("张三", "计算机2401")
```

## 12. 这次改造去掉了哪些陌生写法

下面这些独立 SQLAlchemy 写法已经不再出现在业务代码中：

- `create_engine(...)`
- `SessionLocal = sessionmaker(...)`
- `Base = declarative_base()`
- `class Student(Base)`
- `with SessionLocal() as db_session`
- `db_session.query(...)`

现在统一改成你在 Flask 用户账户项目中使用过的：

- `db = SQLAlchemy(app)`
- `class Student(db.Model)`
- `Student.query.filter_by(...).first()`
- `db.session.get(...)`
- `db.session.add(...)`
- `db.session.commit()`
- `db.session.rollback()`
- `db.session.delete(...)`
