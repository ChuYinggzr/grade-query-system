# 成绩查询系统

一个 Python + PyMySQL 的命令行成绩查询项目。

## 功能

- 添加学生 / 课程
- 录入成绩（带存在性、分数范围校验）
- 查询某学生 / 某课程 / 全部成绩
- 修改成绩
- 删除学生 / 课程 / 成绩记录（级联删除关联成绩）

## 使用步骤

1. 在 DataGrip 或 MySQL 命令行执行 `schema.sql`，创建 `grade_system` 库、表及示例数据。
2. 安装依赖：`python -m pip install pymysql`
3. 设置数据库密码环境变量：`DB_PASSWORD`（避免写死在代码里）
4. 运行 `mysql.py`

## 数据库配置

密码通过环境变量 `DB_PASSWORD` 读取，例如：

```bash
set DB_PASSWORD=你的密码
```

然后运行：

```bash
python mysql.py
```

## 核心 SQL

用 JOIN 把三张表关联起来查询成绩：

```sql
SELECT s.name, c.name, sc.score
FROM score sc
JOIN student s ON sc.student_id = s.id
JOIN course c ON sc.course_id = c.id
WHERE sc.student_id = 1;
```
