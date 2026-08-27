# 成绩查询系统 - Python + PyMySQL
# 运行前：pip install pymysql

import pymysql
import os

# ------------------- 数据库配置（建议通过环境变量设置，避免硬编码） -------------------
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),   # 密码请通过环境变量 DB_PASSWORD 设置，不要写死在代码里
    "database": os.getenv("DB_NAME", "grade_system"),
    "charset": "utf8mb4",
}


def get_conn():
    """获取数据库连接"""
    return pymysql.connect(**DB_CONFIG)


# ------------------- 辅助函数：检查学生/课程是否存在 -------------------
def student_exists(student_id):
    """检查学生ID是否存在"""
    sql = "SELECT 1 FROM student WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (student_id,))
            return cur.fetchone() is not None


def course_exists(course_id):
    """检查课程ID是否存在"""
    sql = "SELECT 1 FROM course WHERE id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (course_id,))
            return cur.fetchone() is not None


def score_exists(student_id, course_id):
    """检查成绩记录是否已存在（同一学生同一课程）"""
    sql = "SELECT 1 FROM score WHERE student_id = %s AND course_id = %s"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (student_id, course_id))
            return cur.fetchone() is not None


# ------------------- 增删改查功能 -------------------
def add_student(name, class_name):
    """添加学生，带输入验证和异常处理"""
    # 1. 拦截姓名为空（保留原逻辑）
    if not name.strip():
        print("错误：学生姓名不能为空")
        return

    # 2. 清洗班级：去掉首尾空格；如果为空或全是空格，赋予默认值 "未分班"
    # 如果去除首尾空格后是空的，就赋值为 "未分班"
    if not class_name.strip():
        class_name = "未分班"           # 避免出现多余空格或者班级为空不知道

    # 3. 执行数据库插入
    try:
        sql = "INSERT INTO student (name, class_name) VALUES (%s, %s)"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (name, class_name))
            conn.commit()
        print(f"已添加学生：{name}")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")

def add_course(name):
    """添加课程，带输入验证和异常处理"""
    if not name.strip():
        print("错误：课程名不能为空")
        return
    try:
        sql = "INSERT INTO course (name) VALUES (%s)"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (name,))
            conn.commit()
        print(f"已添加课程：{name}")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")


def add_score(student_id, course_id, score):
    """录入成绩，带完整验证：学生和课程必须存在，成绩0-100，且不允许重复录入"""
    # 验证学生和课程是否存在
    if not student_exists(student_id):
        print(f"错误：学生ID {student_id} 不存在")
        return
    if not course_exists(course_id):
        print(f"错误：课程ID {course_id} 不存在")
        return

    # 验证成绩范围
    if not (0 <= score <= 100):
        print("错误：成绩必须在0到100之间")
        return

    # 检查是否已存在该学生该课程的成绩
    if score_exists(student_id, course_id):
        print(f"错误：学生 {student_id} 的课程 {course_id} 成绩已存在，请使用修改功能")
        return

    try:
        sql = "INSERT INTO score (student_id, course_id, score) VALUES (%s, %s, %s)"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (student_id, course_id, score))
            conn.commit()
        print("已录入成绩")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")


def update_score(student_id, course_id, new_score):
    """修改成绩，带验证"""
    if not student_exists(student_id):
        print(f"错误：学生ID {student_id} 不存在")
        return
    if not course_exists(course_id):
        print(f"错误：课程ID {course_id} 不存在")
        return
    if not (0 <= new_score <= 100):
        print("错误：成绩必须在0到100之间")
        return
    if not score_exists(student_id, course_id):
        print(f"错误：学生 {student_id} 的课程 {course_id} 还没有成绩记录，无法修改")
        return

    try:
        sql = "UPDATE score SET score = %s WHERE student_id = %s AND course_id = %s"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (new_score, student_id, course_id))
            conn.commit()
        print("成绩修改成功")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")


def delete_student(student_id):
    """删除学生（同时删除其所有成绩记录）"""
    if not student_exists(student_id):
        print(f"错误：学生ID {student_id} 不存在")
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 外键已设置 ON DELETE CASCADE，删除学生时成绩会自动删除
                cur.execute("DELETE FROM student WHERE id = %s", (student_id,))
            conn.commit()
        print(f"学生 {student_id} 及其成绩已删除")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")


def delete_course(course_id):
    """删除课程（同时删除该课程的所有成绩记录）"""
    if not course_exists(course_id):
        print(f"错误：课程ID {course_id} 不存在")
        return
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 外键已设置 ON DELETE CASCADE，删除课程时成绩会自动删除
                cur.execute("DELETE FROM course WHERE id = %s", (course_id,))
            conn.commit()
        print(f"课程 {course_id} 及其成绩已删除")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")


def delete_score(student_id, course_id):
    """删除某学生某课程的成绩记录"""
    if not score_exists(student_id, course_id):
        print(f"错误：学生 {student_id} 的课程 {course_id} 没有成绩记录")
        return
    try:
        sql = "DELETE FROM score WHERE student_id = %s AND course_id = %s"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (student_id, course_id))
            conn.commit()
        print("成绩删除成功")
    except pymysql.MySQLError as e:
        print(f"数据库错误：{e}")


def query_student(student_id):
    """查询某学生的所有成绩"""
    if not student_exists(student_id):
        print(f"错误：学生ID {student_id} 不存在")
        return
    sql = """
        SELECT s.name, c.name, sc.score
        FROM score sc
        JOIN student s ON sc.student_id = s.id
        JOIN course c ON sc.course_id = c.id
        WHERE sc.student_id = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (student_id,))
            rows = cur.fetchall()
    print("\n=== 学生成绩 ===")
    for name, course, score in rows:
        print(f"{name} | {course} | {score}")
    if not rows:
        print("没有记录")


def query_course(course_id):
    """查询某课程的所有成绩"""
    if not course_exists(course_id):
        print(f"错误：课程ID {course_id} 不存在")
        return
    sql = """
        SELECT s.name, c.name, sc.score
        FROM score sc
        JOIN student s ON sc.student_id = s.id
        JOIN course c ON sc.course_id = c.id
        WHERE sc.course_id = %s
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (course_id,))
            rows = cur.fetchall()
    print("\n=== 课程成绩 ===")
    for name, course, score in rows:
        print(f"{name} | {course} | {score}")
    if not rows:
        print("没有记录")


def query_all():
    """查询全部成绩"""
    sql = """
        SELECT s.name, c.name, sc.score
        FROM score sc
        JOIN student s ON sc.student_id = s.id
        JOIN course c ON sc.course_id = c.id
        ORDER BY s.id, c.id
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    print("\n=== 全部成绩 ===")
    for name, course, score in rows:
        print(f"{name} | {course} | {score}")
    if not rows:
        print("暂无成绩记录")


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
                score = float(input("分数：").strip())
                add_score(student_id, course_id, score)
            except ValueError:
                print("错误：学号、课程号和分数必须是数字")

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
                new_score = float(input("新分数：").strip())
                update_score(student_id, course_id, new_score)
            except ValueError:
                print("错误：学号、课程号和分数必须是数字")

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
    menu()