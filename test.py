#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, unicode_literals
import os
import unittest
import tempfile
import shutil
import subprocess


def shell(cmd, input=None):
    p = subprocess.Popen(
        cmd, shell=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input)
    return p.returncode, stdout, stderr


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class TestGitPreReceiveHook(unittest.TestCase):

    @classmethod
    def _setUpTestGitTagger(cls, name, email):

        code, old_git_user_name, _ = shell("git config --system user.name")
        cls.old_git_user_name = old_git_user if code == 0 else None
        shell("git config --system user.name %s" % name)

        code, old_git_user_email, _ = shell("git config --system user.email")
        cls.old_git_user_email = old_git_user_email if code == 0 else None
        shell("git config --system user.email %s" % email)

    @classmethod
    def _resumeGitConfig(cls):
        if cls.old_git_user_name:
            shell("git config --system user.name %s" % cls.old_git_user_name)
        else:
            shell("git config --system --unset user.name")
        if cls.old_git_user_email:
            shell("git config --system user.email %s" % cls.old_git_user_email)
        else:
            shell("git config --system --unset user.email")

    @classmethod
    def setUpClass(cls):
        cls._setUpTestGitTagger("AdminTester", "admin@yy.com")

    @classmethod
    def tearDownClass(cls):
        cls._resumeGitConfig()

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir(SCRIPT_DIR)
        shutil.rmtree(self.test_dir)

    def _create_git_repo(self, name):
        repo_path = os.path.join(self.test_dir, '%s.git' % name)
        shell('git init --bare %s' % repo_path)
        shell('ln -s %s/pre-receive %s.git/hooks/' % (SCRIPT_DIR, name))
        return repo_path

    def test_protect_master_branch(self):

        # Init test bare repo and clone
        work_dir_name = 'test1'
        repo_path = self._create_git_repo(work_dir_name)
        shell('git clone %s %s' % (repo_path, work_dir_name))
        os.chdir(work_dir_name)

        # Nomal Push
        open('a', 'w').close()
        self.assertEqual(
            shell('git add a && git commit -m "a" && git push')[0], 0)
        open('b', 'w').close()
        self.assertEqual(
            shell('git add b && git commit -m "b" && git push')[0], 0)

        # Delete Master Branch
        self.assertEqual(
            shell('git push -d origin master')[0], 1)

        # Force Push Master Branch
        shell("git checkout --orphan master1 && git rm -r --cached .")
        open('c', 'w').close()
        shell('git add c && git commit -m "c"')
        self.assertEqual(
            shell('git push -f origin master1:master')[0], 1)


if __name__ == '__main__':
    unittest.main()
