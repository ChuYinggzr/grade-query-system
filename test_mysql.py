"""不连接个人MySQL，使用SQLite内存数据库验证全部业务功能。"""

import io
import os
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.dialects import mysql as mysql_dialect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.schema import CreateTable


# 必须放在导入项目代码之前，使测试使用临时SQLite而不是个人MySQL。
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import mysql as project


class GradeSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_context = project.app.app_context()
        cls.app_context.push()

        @event.listens_for(project.db.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    @classmethod
    def tearDownClass(cls):
        project.db.session.remove()
        cls.app_context.pop()

    def setUp(self):
        project.db.session.remove()
        project.db.drop_all()
        project.db.create_all()

        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()

    def tearDown(self):
        self.capture.__exit__(None, None, None)
        project.db.session.remove()

    def seed(self):
        student_id = project.add_student("张三", "计算机2401")
        course_id = project.add_course("Python程序设计")
        return student_id, course_id

    def test_add_and_query_all_three_ways(self):
        student_id, course_id = self.seed()
        self.assertTrue(project.add_score(student_id, course_id, "88.50"))

        for rows in (
            project.query_student(student_id),
            project.query_course(course_id),
            project.query_all(),
        ):
            self.assertEqual(len(rows), 1)
            self.assertEqual(tuple(rows[0])[:2], ("张三", "Python程序设计"))
            self.assertEqual(Decimal(str(rows[0][2])), Decimal("88.50"))

    def test_trim_and_default_class(self):
        student_id = project.add_student(" 张三 ", " ")
        student = project.db.session.get(project.Student, student_id)
        self.assertEqual(student.name, "张三")
        self.assertEqual(student.class_name, "未分班")

    def test_name_validation(self):
        invalid_students = [
            (" ", "班级"),
            ("名" * 51, "班级"),
            ("名字", "班" * 51),
        ]
        for name, class_name in invalid_students:
            with self.subTest(name=name):
                self.assertIsNone(project.add_student(name, class_name))

        for name in (" ", "课" * 51):
            self.assertIsNone(project.add_course(name))

    def test_score_validation(self):
        student_id, course_id = self.seed()
        invalid_scores = ("abc", None, True, "NaN", "Infinity", "-1", "101", "88.555")

        for value in invalid_scores:
            with self.subTest(value=value):
                self.assertFalse(project.add_score(student_id, course_id, value))

        self.assertEqual(project.query_all(), [])
        self.assertTrue(project.add_score(student_id, course_id, "0"))
        self.assertTrue(project.update_score(student_id, course_id, "100"))

    def test_missing_student_course_or_record(self):
        student_id, course_id = self.seed()
        self.assertFalse(project.add_score(999999, course_id, "80"))
        self.assertFalse(project.add_score(student_id, 999999, "80"))
        self.assertFalse(project.update_score(student_id, course_id, "80"))
        self.assertFalse(project.delete_score(student_id, course_id))
        self.assertFalse(project.delete_student(999999))
        self.assertFalse(project.delete_course(999999))
        self.assertEqual(project.query_student(999999), [])
        self.assertEqual(project.query_course(999999), [])

    def test_duplicate_and_update(self):
        student_id, course_id = self.seed()
        self.assertTrue(project.add_score(student_id, course_id, "80"))
        self.assertFalse(project.add_score(student_id, course_id, "90"))
        self.assertTrue(project.update_score(student_id, course_id, "92.25"))

        records = project.Score.query.all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].score, Decimal("92.25"))

    def test_database_unique_and_foreign_key_constraints(self):
        student_id, course_id = self.seed()
        project.add_score(student_id, course_id, "80")

        duplicate = project.Score(
            student_id=student_id,
            course_id=course_id,
            score=90,
        )
        project.db.session.add(duplicate)
        with self.assertRaises(IntegrityError):
            project.db.session.commit()
        project.db.session.rollback()

        invalid_foreign_key = project.Score(
            student_id=999999,
            course_id=course_id,
            score=90,
        )
        project.db.session.add(invalid_foreign_key)
        with self.assertRaises(IntegrityError):
            project.db.session.commit()
        project.db.session.rollback()

    def test_delete_score_keeps_student_and_course(self):
        student_id, course_id = self.seed()
        project.add_score(student_id, course_id, "80")
        self.assertTrue(project.delete_score(student_id, course_id))

        self.assertIsNotNone(project.db.session.get(project.Student, student_id))
        self.assertIsNotNone(project.db.session.get(project.Course, course_id))
        self.assertEqual(project.Score.query.count(), 0)

    def test_delete_student_cascades_only_its_scores(self):
        student_id, course_id = self.seed()
        other_id = project.add_student("李四", "班级")
        project.add_score(student_id, course_id, "80")
        project.add_score(other_id, course_id, "90")

        self.assertTrue(project.delete_student(student_id))
        self.assertIsNone(project.db.session.get(project.Student, student_id))
        self.assertIsNotNone(project.db.session.get(project.Course, course_id))
        self.assertEqual(project.Score.query.one().student_id, other_id)

    def test_delete_course_cascades_only_its_scores(self):
        student_id, course_id = self.seed()
        other_id = project.add_course("MySQL数据库")
        project.add_score(student_id, course_id, "80")
        project.add_score(student_id, other_id, "90")

        self.assertTrue(project.delete_course(course_id))
        self.assertIsNone(project.db.session.get(project.Course, course_id))
        self.assertIsNotNone(project.db.session.get(project.Student, student_id))
        self.assertEqual(project.Score.query.one().course_id, other_id)

    def test_commit_error_rolls_back_and_next_action_works(self):
        student_id, course_id = self.seed()
        original_rollback = project.db.session.rollback

        with patch.object(
            project.db.session,
            "commit",
            side_effect=IntegrityError("insert", {}, Exception("duplicate")),
        ):
            with patch.object(
                project.db.session,
                "rollback",
                side_effect=original_rollback,
            ) as rollback:
                self.assertFalse(project.add_score(student_id, course_id, "80"))
                rollback.assert_called_once()

        self.assertEqual(project.query_all(), [])
        self.assertTrue(project.add_score(student_id, course_id, "80"))

    def test_database_error_is_handled_for_write_and_read(self):
        error = OperationalError("statement", {}, Exception("offline"))

        with patch.object(project.db.session, "commit", side_effect=error):
            self.assertIsNone(project.add_course("失败课程"))

        self.assertEqual(project.Course.query.count(), 0)

        with patch.object(project.db.session, "execute", side_effect=error):
            self.assertEqual(project.query_all(), [])

        self.assertIsNotNone(project.add_course("恢复课程"))

    def test_init_tables_preserves_existing_data(self):
        student_id, _ = self.seed()
        self.assertTrue(project.init_tables())
        self.assertTrue(project.init_tables())
        self.assertIsNotNone(project.db.session.get(project.Student, student_id))

    def test_mysql_ddl_matches_original_schema(self):
        score_ddl = str(
            CreateTable(project.Score.__table__).compile(
                dialect=mysql_dialect.dialect()
            )
        )
        self.assertIn("NUMERIC(5, 2)", score_ddl)
        self.assertIn("uk_student_course", score_ddl)
        self.assertEqual(score_ddl.count("ON DELETE CASCADE"), 2)

        student_ddl = str(
            CreateTable(project.Student.__table__).compile(
                dialect=mysql_dialect.dialect()
            )
        )
        self.assertIn("AUTO_INCREMENT", student_ddl)

    def test_menu_can_exit_without_database_operation(self):
        with patch("builtins.input", return_value="0"):
            project.menu()
        self.assertIn("再见", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
