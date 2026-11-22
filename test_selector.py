import unittest
from selector import choose_workers, parse_patch, select


class SelectorTests(unittest.TestCase):
    def test_old_lines_and_insertions_across_files(self):
        patch = '''diff --git a/sqlglot/a.py b/sqlglot/a.py
--- a/sqlglot/a.py
+++ b/sqlglot/a.py
@@ -10,3 +10,4 @@
 unchanged
-old
+new
+extra
 unchanged
diff --git a/sqlglot/b.py b/sqlglot/b.py
--- a/sqlglot/b.py
+++ b/sqlglot/b.py
@@ -5,1 +5,0 @@
-gone
'''
        rows = list(parse_patch(patch))
        self.assertEqual(rows[0][2], {11})
        self.assertEqual(rows[0][3], {11, 12})
        self.assertEqual(rows[1][2], {5})

    def test_rename_without_hunks(self):
        rows = list(parse_patch('diff --git a/sqlglot/a.py b/sqlglot/b.py\nrename from sqlglot/a.py\nrename to sqlglot/b.py\n'))
        self.assertEqual(rows, [('sqlglot/a.py', 'sqlglot/b.py', set(), set())])

    def test_worker_cost_uses_integer_milliseconds(self):
        self.assertEqual(choose_workers(set(), {}), [])
        self.assertEqual(choose_workers({0, 1}, {0: 1000, 1: 1000}), [[0, 1]])
        self.assertEqual(len(choose_workers({0, 1}, {0: 10000, 1: 10000})), 2)

    def test_shared_optimizer_fallback(self):
        ids = {'tests/test_optimizer.py::T::test_optimize': 1,
               'tests/test_executor.py::T::test_execute_tpcds': 2}
        files = {'tests/test_optimizer.py': {next(iter(ids))},
                 'tests/test_executor.py': {'tests/test_executor.py::T::test_execute_tpcds'}}
        maps = {'lines': {}, 'files': {}, 'functions': {}, 'imports': {}}
        change = [('sqlglot/optimizer/eliminate_joins.py',
                   'sqlglot/optimizer/eliminate_joins.py', {68}, set())]
        self.assertEqual(select(change, maps, ids, files), {1, 2})

    def test_fixture_exact_test_name(self):
        maps = {'lines': {}, 'files': {}, 'functions': {}, 'imports': {}}
        ids = {'tests/test_optimizer.py::T::test_simplify': 1,
               'tests/test_optimizer.py::T::test_other': 2}
        files = {'tests/test_optimizer.py': set(ids)}
        self.assertEqual(select([('tests/fixtures/optimizer/simplify.sql', 'tests/fixtures/optimizer/simplify.sql', {1}, set())], maps, ids, files), {1})


if __name__ == '__main__':
    unittest.main()
