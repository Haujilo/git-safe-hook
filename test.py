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
        cls.git_user_name = name

        code, old_git_user_email, _ = shell("git config --system user.email")
        cls.old_git_user_email = old_git_user_email if code == 0 else None
        shell("git config --system user.email %s" % email)
        cls.git_user_email = email

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

    def _create_and_clone_git_repo(self, name):
        repo_path = self._create_git_repo(name)
        shell('git clone %s %s' % (repo_path, name))
        os.chdir(name)

    def test_protect_master_branch(self):

        self._create_and_clone_git_repo('test1')

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

    def test_protect_release_tag(self):

        self._create_and_clone_git_repo('test2')
        open('a', 'w').close()
        shell('git add a && git commit -m "a"')
        open('b', 'w').close()
        shell('git add b && git commit -m "b"')

        # Nomal Push
        shell('git config --local user.name %s' % self.git_user_name)
        shell('git config --local user.email %s' % self.git_user_email)
        shell('git tag -a 1.0.0 -m "1.0.0" master~1')
        self.assertEqual(shell('git push --tags')[0], 0)

        # Delete Release Tag
        self.assertEqual(shell('git push -d origin 1.0.0')[0], 1)

        # Force Push Release Tag
        shell('git tag -d 1.0.0')
        shell('git tag -a 1.0.0 -m "1.0.0" master')
        self.assertEqual(shell('git push -f --tags')[0], 1)

    def test_protect_release_branch(self):
        self._create_and_clone_git_repo('test3')
        open('a', 'w').close()
        shell('git add a && git commit -m "a" && git push')

        # Nomal Push
        shell('git checkout -b release/1.0.0')
        self.assertEqual(
            shell('git push --set-upstream origin release/1.0.0')[0], 0)
        open('b', 'w').close()
        shell('git add b && git commit -m "b"')
        self.assertEqual(shell('git push')[0], 0)

        # Nomal Delete
        self.assertEqual(
            shell('git push -d origin release/1.0.0')[0], 0)

        # Tag A Release Branch
        self.assertEqual(shell('git push')[0], 0)
        shell('git config --local user.name %s' % self.git_user_name)
        shell('git config --local user.email %s' % self.git_user_email)
        shell('git tag -a 1.0.0 -m "1.0.0" release/1.0.0')
        self.assertEqual(shell('git push --tags')[0], 0)

        # Delete Tagged Release Branch
        self.assertEqual(
            shell('git push -d origin release/1.0.0')[0], 1)
        shell('git checkout master && git merge 1.0.0 && git push')
        self.assertEqual(
            shell('git push -d origin release/1.0.0')[0], 0)

        # Tag Other Release Branch
        shell('git checkout -b release/1.0.1 master')
        open('c', 'w').close()
        shell('git add c && git commit -m "c"')
        shell('git push --set-upstream origin release/1.0.1')
        shell('git tag -a 1.0.1 -m "1.0.1" release/1.0.1')
        self.assertEqual(shell('git push --tags')[0], 0)

        # Force Push
        shell('git checkout -b branch1 master')
        open('d', 'w').close()
        shell('git add d && git commit -m "d"')
        self.assertEqual(
            shell('git push -f origin branch1:release/1.0.1')[0], 1)
        shell('git checkout master && git merge 1.0.1 && git push')
        self.assertEqual(
            shell('git push -f origin branch1:release/1.0.1')[0], 0)

        # Release Branch Not Checkout From Master Branch
        shell('git checkout --orphan release/0.1.0 && git rm -r --cached .')
        open('aa', 'w').close()
        shell('git add aa && git commit -m "aa"')
        self.assertEqual(
            shell('git push --set-upstream origin release/0.1.0')[0], 1)


if __name__ == '__main__':
    unittest.main()
