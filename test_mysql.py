"""不连接个人 MySQL：使用临时内存数据库验证业务逻辑。"""
import io
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, event, text
from sqlalchemy.dialects import mysql as mysql_dialect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import CreateTable

import mysql as project


class GradeSystemTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        project.Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.session_patch = patch.object(project, "SessionLocal", self.sessions)
        self.session_patch.start()
        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()

    def tearDown(self):
        self.capture.__exit__(None, None, None)
        self.session_patch.stop()
        self.engine.dispose()

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
        with self.sessions() as session:
            student = session.get(project.Student, student_id)
            self.assertEqual(student.name, "张三")
            self.assertEqual(student.class_name, "未分班")

    def test_name_validation(self):
        for name, class_name in [(" ", "班级"), ("名" * 51, "班级"), ("名字", "班" * 51)]:
            with self.subTest(name=name):
                self.assertIsNone(project.add_student(name, class_name))
        for name in (" ", "课" * 51):
            self.assertIsNone(project.add_course(name))

    def test_score_validation(self):
        student_id, course_id = self.seed()
        for value in ("abc", None, True, "NaN", "Infinity", "-1", "101", "88.555"):
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
        with self.sessions() as session:
            records = session.query(project.Score).all()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].score, Decimal("92.25"))

    def test_database_unique_and_foreign_key_constraints(self):
        student_id, course_id = self.seed()
        project.add_score(student_id, course_id, "80")
        with self.sessions() as session:
            session.add(project.Score(student_id=student_id, course_id=course_id, score=90))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()
            session.add(project.Score(student_id=999999, course_id=course_id, score=90))
            with self.assertRaises(IntegrityError):
                session.commit()
            session.rollback()

    def test_delete_score_keeps_student_and_course(self):
        student_id, course_id = self.seed()
        project.add_score(student_id, course_id, "80")
        self.assertTrue(project.delete_score(student_id, course_id))
        with self.sessions() as session:
            self.assertIsNotNone(session.get(project.Student, student_id))
            self.assertIsNotNone(session.get(project.Course, course_id))
            self.assertEqual(session.query(project.Score).count(), 0)

    def test_delete_student_cascades_only_its_scores(self):
        student_id, course_id = self.seed()
        other_id = project.add_student("李四", "班级")
        project.add_score(student_id, course_id, "80")
        project.add_score(other_id, course_id, "90")
        self.assertTrue(project.delete_student(student_id))
        with self.sessions() as session:
            self.assertIsNone(session.get(project.Student, student_id))
            self.assertIsNotNone(session.get(project.Course, course_id))
            self.assertEqual(session.query(project.Score).one().student_id, other_id)

    def test_delete_course_cascades_only_its_scores(self):
        student_id, course_id = self.seed()
        other_id = project.add_course("MySQL数据库")
        project.add_score(student_id, course_id, "80")
        project.add_score(student_id, other_id, "90")
        self.assertTrue(project.delete_course(course_id))
        with self.sessions() as session:
            self.assertIsNone(session.get(project.Course, course_id))
            self.assertIsNotNone(session.get(project.Student, student_id))
            self.assertEqual(session.query(project.Score).one().course_id, other_id)

    def test_commit_error_rolls_back_and_next_action_works(self):
        student_id, course_id = self.seed()
        rollback_calls = []
        original_rollback = Session.rollback

        def record_rollback(session):
            rollback_calls.append(True)
            return original_rollback(session)

        with patch.object(Session, "commit", side_effect=IntegrityError("insert", {}, Exception("duplicate"))):
            with patch.object(Session, "rollback", record_rollback):
                self.assertFalse(project.add_score(student_id, course_id, "80"))
        self.assertEqual(len(rollback_calls), 1)
        self.assertEqual(project.query_all(), [])
        self.assertTrue(project.add_score(student_id, course_id, "80"))

    def test_database_error_is_handled_for_write_and_read(self):
        error = OperationalError("statement", {}, Exception("offline"))
        with patch.object(Session, "commit", side_effect=error):
            self.assertIsNone(project.add_course("失败课程"))
        with self.sessions() as session:
            self.assertEqual(session.query(project.Course).count(), 0)
        with patch.object(Session, "execute", side_effect=error):
            self.assertEqual(project.query_all(), [])
            self.assertFalse(project.add_score(1, 1, "80"))
        self.assertIsNotNone(project.add_course("恢复课程"))

    def test_init_tables_preserves_existing_data(self):
        student_id, _ = self.seed()
        with patch.object(project, "engine", self.engine):
            self.assertTrue(project.init_tables())
            self.assertTrue(project.init_tables())
        with self.sessions() as session:
            self.assertIsNotNone(session.get(project.Student, student_id))

    def test_mysql_ddl_matches_original_schema(self):
        ddl = str(CreateTable(project.Score.__table__).compile(dialect=mysql_dialect.dialect()))
        self.assertIn("NUMERIC(5, 2)", ddl)
        self.assertIn("uk_student_course", ddl)
        self.assertEqual(ddl.count("ON DELETE CASCADE"), 2)
        ddl = str(CreateTable(project.Student.__table__).compile(dialect=mysql_dialect.dialect()))
        self.assertIn("AUTO_INCREMENT", ddl)

    def test_menu_can_exit_without_database_connection(self):
        with patch("builtins.input", return_value="0"):
            project.menu()
        self.assertIn("再见", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
