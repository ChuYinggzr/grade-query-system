# 成绩查询系统：保留命令行操作，数据库操作改为 SQLAlchemy。
import os
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

# 读取项目目录下的 .env；已有的系统环境变量优先。
load_dotenv(Path(__file__).with_name(".env"))

# URL.create() 正确处理密码中的 @、# 等字符，避免手动拼接地址。
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
# 会话工厂：每次操作创建一个会话，不在等待菜单输入时占用事务。
SessionLocal = sessionmaker(bind=engine)
# 没有 Flask-SQLAlchemy 的 db.Model，所以创建一个模型基类。
Base = declarative_base()


# ------------------- 模型：对应原来的三张表 -------------------
class Student(Base):
    __tablename__ = "student"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    class_name = Column(String(50))


class Course(Base):
    __tablename__ = "course"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)


class Score(Base):
    __tablename__ = "score"
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(
        Integer,
        ForeignKey("student.id", name="fk_score_student", ondelete="CASCADE"),
        nullable=False,
    )
    course_id = Column(
        Integer,
        ForeignKey("course.id", name="fk_score_course", ondelete="CASCADE"),
        nullable=False,
    )
    score = Column(Numeric(5, 2), nullable=False)
    # 同一学生同一课程只能有一条成绩，不要求姓名、课程名唯一。
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uk_student_course"),
    )


def init_tables():
    """仅创建缺少的表，不删除数据，也不修改已有表的结构。"""
    try:
        Base.metadata.create_all(engine)
        print("表初始化完成：已有的表和数据不会被重建")
        return True
    except SQLAlchemyError:
        print("数据库初始化失败：请检查 MySQL 服务、配置、权限和数据库是否已创建")
        return False


def validate_score(value):
    """用 Decimal 对应数据库 DECIMAL(5,2)，避免先转 float。"""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        print("错误：分数必须是数字")
        return None
    if not number.is_finite() or not 0 <= number <= 100:
        print("错误：成绩必须在0到100之间")
        return None
    if number != number.quantize(Decimal("0.01")):
        print("错误：成绩最多保留两位小数")
        return None
    return number


# ------------------- 辅助查询：复用调用者的会话 -------------------
def student_exists(db_session, student_id):
    return db_session.get(Student, student_id) is not None


def course_exists(db_session, course_id):
    return db_session.get(Course, course_id) is not None


def find_score(db_session, student_id, course_id):
    # 与 Flask 中 User.query.filter_by(...).first() 的用途相同。
    return db_session.query(Score).filter_by(
        student_id=student_id, course_id=course_id
    ).first()


# ------------------- 增删改：显式提交和异常回滚 -------------------
def add_student(name, class_name):
    name = name.strip()
    class_name = class_name.strip() or "未分班"
    if not name:
        print("错误：学生姓名不能为空")
        return None
    if len(name) > 50 or len(class_name) > 50:
        print("错误：学生姓名和班级不能超过50个字符")
        return None
    with SessionLocal() as db_session:
        try:
            student = Student(name=name, class_name=class_name)
            db_session.add(student)  # 对应 db.session.add(user)。
            db_session.commit()     # 真正保存到数据库。
            print(f"已添加学生：{name}，学号：{student.id}")
            return student.id
        except SQLAlchemyError:
            db_session.rollback()
            print("添加学生失败：请检查数据库连接、表结构和权限")
            return None


def add_course(name):
    name = name.strip()
    if not name or len(name) > 50:
        print("错误：课程名不能为空，且不能超过50个字符")
        return None
    with SessionLocal() as db_session:
        try:
            course = Course(name=name)
            db_session.add(course)
            db_session.commit()
            print(f"已添加课程：{name}，课程号：{course.id}")
            return course.id
        except SQLAlchemyError:
            db_session.rollback()
            print("添加课程失败：请检查数据库连接、表结构和权限")
            return None


def add_score(student_id, course_id, score):
    score = validate_score(score)
    if score is None:
        return False
    with SessionLocal() as db_session:
        try:
            if not student_exists(db_session, student_id):
                print(f"错误：学生ID {student_id} 不存在")
                return False
            if not course_exists(db_session, course_id):
                print(f"错误：课程ID {course_id} 不存在")
                return False
            if find_score(db_session, student_id, course_id) is not None:
                print("错误：该学生的这门课程成绩已存在，请使用修改功能")
                return False
            record = Score(student_id=student_id, course_id=course_id, score=score)
            db_session.add(record)
            db_session.commit()
            print("已录入成绩")
            return True
        except IntegrityError:
            # 查询之后可能有其他程序同时录入，最终由数据库唯一约束兜底。
            db_session.rollback()
            print("录入失败：成绩重复，或学生、课程已被删除")
            return False
        except SQLAlchemyError:
            db_session.rollback()
            print("录入失败：请检查数据库连接、表结构和权限")
            return False


def update_score(student_id, course_id, new_score):
    new_score = validate_score(new_score)
    if new_score is None:
        return False
    with SessionLocal() as db_session:
        try:
            record = find_score(db_session, student_id, course_id)
            if record is None:
                print("错误：没有这条成绩记录，无法修改")
                return False
            record.score = new_score  # 修改查到的对象，而不是新建对象。
            db_session.commit()
            print("成绩修改成功")
            return True
        except SQLAlchemyError:
            db_session.rollback()
            print("修改失败：请检查数据库连接、表结构和权限")
            return False


def delete_student(student_id):
    with SessionLocal() as db_session:
        try:
            student = db_session.get(Student, student_id)
            if student is None:
                print(f"错误：学生ID {student_id} 不存在")
                return False
            # 数据库外键 ON DELETE CASCADE 负责删除该学生的成绩。
            db_session.delete(student)
            db_session.commit()
            print(f"学生 {student_id} 及其成绩已删除")
            return True
        except SQLAlchemyError:
            db_session.rollback()
            print("删除学生失败：请检查数据库连接和外键约束")
            return False


def delete_course(course_id):
    with SessionLocal() as db_session:
        try:
            course = db_session.get(Course, course_id)
            if course is None:
                print(f"错误：课程ID {course_id} 不存在")
                return False
            db_session.delete(course)
            db_session.commit()
            print(f"课程 {course_id} 及其成绩已删除")
            return True
        except SQLAlchemyError:
            db_session.rollback()
            print("删除课程失败：请检查数据库连接和外键约束")
            return False


def delete_score(student_id, course_id):
    with SessionLocal() as db_session:
        try:
            record = find_score(db_session, student_id, course_id)
            if record is None:
                print("错误：没有这条成绩记录")
                return False
            db_session.delete(record)
            db_session.commit()
            print("成绩删除成功")
            return True
        except SQLAlchemyError:
            db_session.rollback()
            print("删除成绩失败：请检查数据库连接、表结构和权限")
            return False


# ------------------- 多表查询：保留 SQL，通过 SQLAlchemy 执行 -------------------
def query_student(student_id):
    with SessionLocal() as db_session:
        try:
            if not student_exists(db_session, student_id):
                print(f"错误：学生ID {student_id} 不存在")
                return []
            rows = db_session.execute(text("""
                SELECT s.name, c.name, sc.score
                FROM score sc
                JOIN student s ON sc.student_id = s.id
                JOIN course c ON sc.course_id = c.id
                WHERE sc.student_id = :student_id
                ORDER BY c.id
            """), {"student_id": student_id}).all()
            print("\n=== 学生成绩 ===")
            for name, course, score in rows:
                print(f"{name} | {course} | {score}")
            if not rows:
                print("没有记录")
            return rows
        except SQLAlchemyError:
            db_session.rollback()
            print("查询失败：请检查数据库连接、表结构和权限")
            return []


def query_course(course_id):
    with SessionLocal() as db_session:
        try:
            if not course_exists(db_session, course_id):
                print(f"错误：课程ID {course_id} 不存在")
                return []
            rows = db_session.execute(text("""
                SELECT s.name, c.name, sc.score
                FROM score sc
                JOIN student s ON sc.student_id = s.id
                JOIN course c ON sc.course_id = c.id
                WHERE sc.course_id = :course_id
                ORDER BY s.id
            """), {"course_id": course_id}).all()
            print("\n=== 课程成绩 ===")
            for name, course, score in rows:
                print(f"{name} | {course} | {score}")
            if not rows:
                print("没有记录")
            return rows
        except SQLAlchemyError:
            db_session.rollback()
            print("查询失败：请检查数据库连接、表结构和权限")
            return []


def query_all():
    with SessionLocal() as db_session:
        try:
            rows = db_session.execute(text("""
                SELECT s.name, c.name, sc.score
                FROM score sc
                JOIN student s ON sc.student_id = s.id
                JOIN course c ON sc.course_id = c.id
                ORDER BY s.id, c.id
            """)).all()
            print("\n=== 全部成绩 ===")
            for name, course, score in rows:
                print(f"{name} | {course} | {score}")
            if not rows:
                print("暂无成绩记录")
            return rows
        except SQLAlchemyError:
            db_session.rollback()
            print("查询失败：请检查数据库连接、表结构和权限")
            return []


# ------------------- 菜单 -------------------
def menu():
    while True:
        print("\n--- 成绩查询系统 ---")
        print("1. 添加学生")
        print("2. 添加课程")
        print("3. 录入成绩")
        print("4. 查询某学生成绩")
        print("5. 查询某课程成绩")
        print("6. 查看全部成绩")
        print("7. 修改成绩")
        print("8. 删除学生")
        print("9. 删除课程")
        print("10. 删除成绩记录")
        print("0. 退出")
        choice = input("请选择：").strip()

        if choice == "1":
            name = input("学生姓名：").strip()
            class_name = input("班级：").strip()
            add_student(name, class_name)

        elif choice == "2":
            name = input("课程名：").strip()
            add_course(name)

        elif choice == "3":
            try:
                student_id = int(input("学号：").strip())
                course_id = int(input("课程号：").strip())
                score = input("分数：").strip()
                add_score(student_id, course_id, score)
            except ValueError:
                print("错误：学号和课程号必须是整数")

        elif choice == "4":
            try:
                student_id = int(input("学号：").strip())
                query_student(student_id)
            except ValueError:
                print("错误：学号必须是数字")

        elif choice == "5":
            try:
                course_id = int(input("课程号：").strip())
                query_course(course_id)
            except ValueError:
                print("错误：课程号必须是数字")

        elif choice == "6":
            query_all()

        elif choice == "7":
            try:
                student_id = int(input("学号：").strip())
                course_id = int(input("课程号：").strip())
                new_score = input("新分数：").strip()
                update_score(student_id, course_id, new_score)
            except ValueError:
                print("错误：学号和课程号必须是整数")

        elif choice == "8":
            try:
                student_id = int(input("要删除的学生学号：").strip())
                delete_student(student_id)
            except ValueError:
                print("错误：学号必须是数字")

        elif choice == "9":
            try:
                course_id = int(input("要删除的课程号：").strip())
                delete_course(course_id)
            except ValueError:
                print("错误：课程号必须是数字")

        elif choice == "10":
            try:
                student_id = int(input("学号：").strip())
                course_id = int(input("课程号：").strip())
                delete_score(student_id, course_id)
            except ValueError:
                print("错误：学号和课程号必须是数字")

        elif choice == "0":
            print("再见")
            break

        else:
            print("无效选项，请重新输入")


if __name__ == "__main__":
    if sys.argv[1:] == ["--init-db"]:
        # 只在明确指定初始化时建表；正常启动菜单不会自动改数据库。
        sys.exit(0 if init_tables() else 1)
    elif sys.argv[1:]:
        print("用法：python mysql.py 或 python mysql.py --init-db")
        sys.exit(1)
    else:
        menu()
