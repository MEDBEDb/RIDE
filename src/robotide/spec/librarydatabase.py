#  Copyright 2008-2012 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
import os
import sqlite3
import time
from robotide.preferences.settings import SETTINGS_DIRECTORY
from robotide.spec.iteminfo import LibraryKeywordInfo

CREATION_SCRIPT = """\
CREATE TABLE libraries (id INTEGER PRIMARY KEY,
                        name TEXT,
                        arguments TEXT,
                        last_updated REAL);
CREATE TABLE keywords (name TEXT,
                       doc TEXT,
                       arguments TEXT,
                       library_name TEXT,
                       library INTEGER,
                       FOREIGN KEY(library) REFERENCES libraries(id));
"""

DATABASE_FILE = os.path.join(SETTINGS_DIRECTORY, 'librarykeywords.db')

def _create_database():
    print 'Creating librarykeywords database to "%s"' % DATABASE_FILE
    connection = sqlite3.connect(DATABASE_FILE)
    connection.executescript(CREATION_SCRIPT)
    connection.commit()
    connection.close()

def _validate_database():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.execute('select id, name, arguments, last_updated from libraries')
    connection.execute('select name, doc, arguments, library_name, library from keywords')
    connection.close()

def initialize_database():
    if not os.path.exists(SETTINGS_DIRECTORY):
        os.makedirs(SETTINGS_DIRECTORY)
    if not os.path.exists(DATABASE_FILE):
        _create_database()
    else:
        try:
            _validate_database()
        except sqlite3.DatabaseError, err:
            print 'error during database validation "%s"' % err
            print 'removing database "%s"' % DATABASE_FILE
            os.remove(DATABASE_FILE)
            _create_database()

class LibraryDatabase(object):

    def __init__(self, database):
        self._connection = sqlite3.connect(database, timeout=30.0)

    def create_database(self):
        self._cursor().executescript(CREATION_SCRIPT)
        self._connection.commit()

    def _cursor(self):
        return self._connection.cursor()

    def close(self):
        self._connection.close()

    def insert_library_keywords(self, library_name, library_arguments, keywords):
        cur = self._cursor()
        old_versions = cur.execute('select id from libraries where name = ? and arguments = ?', (library_name, unicode(library_arguments))).fetchall()
        cur.executemany('delete from keywords where library = ?', old_versions)
        cur.executemany('delete from libraries where id = ?', old_versions)
        lib = self._insert_library(library_name, library_arguments, cur)
        keyword_values = [[kw.name, kw.doc, u' | '.join(kw.arguments), kw.source, lib[0]] for kw in keywords if kw is not None]
        self._insert_library_keywords(keyword_values, cur)
        self._connection.commit()

    def update_library_timestamp(self, name, arguments, milliseconds=None):
        self._cursor().execute('update libraries set last_updated = ? where name = ? and arguments = ?', (milliseconds or time.time(), name, unicode(arguments)))
        self._connection.commit()

    def fetch_library_keywords(self, library_name, library_arguments):
        lib = self._fetch_lib(library_name, library_arguments, self._cursor())
        if lib is None:
            return []
        return [LibraryKeywordInfo(name, doc, library_name, arguments.split(u' | ') if arguments else [])
                for name, doc, arguments, library_name in
                self._connection.execute('select name, doc, arguments, library_name from keywords where library = ?', [lib[0]])]

    def library_exists(self, library_name, library_arguments):
        return self._fetch_lib(library_name, library_arguments, self._cursor()) is not None

    def get_library_last_updated(self, library_name, library_arguments):
        lib = self._fetch_lib(library_name, library_arguments, self._cursor())
        if not lib:
            return 0.0
        return lib[3]

    def _insert_library(self, name, arguments, cursor):
        cursor.execute('insert into libraries values (null, ?, ?, ?)', (name, unicode(arguments), time.time()))
        return self._fetch_lib(name, arguments, cursor)

    def _fetch_lib(self, name, arguments, cursor):
        t = cursor.execute('select max(last_updated) from libraries where name = ? and arguments = ?', (name, unicode(arguments))).fetchone()[0]
        return cursor.execute('select * from libraries where name = ? and arguments = ? and last_updated = ?', (name, unicode(arguments), t)).fetchone()

    def _insert_library_keywords(self, data, cursor):
        cursor.executemany('insert into keywords values (?, ?, ?, ?, ?)', data)
