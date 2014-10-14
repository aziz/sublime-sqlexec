import sublime, sublime_plugin, tempfile, os, subprocess

connection = None
history = ['']

class Connection:
    def __init__(self, options):
        self.settings = sublime.load_settings(options.type + ".sqlexec").get('sql_exec')
        self.command  = sublime.load_settings("SQLExec.sublime-settings").get('sql_exec.commands')[options.type]
        self.options  = options

    def _buildCommand(self, options):
        return self.command + ' ' + ' '.join(options) + ' ' + self.settings['args'].format(options=self.options)

    def _getCommand(self, options, queries, header = ''):
        command  = self._buildCommand(options)
        self.tmp = tempfile.NamedTemporaryFile(mode = 'w', delete = False, suffix='.sql')
        for query in self.settings['before']:
            self.tmp.write(query + "\n")
        for query in queries:
            self.tmp.write(query)
        self.tmp.close()

        cmd = '%s < "%s"' % (command, self.tmp.name)

        return Command(cmd)

    def execute(self, queries):
        command = self._getCommand(self.settings['options'], queries)
        command.show()
        os.unlink(self.tmp.name)

    def desc(self):
        query = self.settings['queries']['desc']['query']
        command = self._getCommand(self.settings['queries']['desc']['options'], query)

        tables = []
        for result in command.run().splitlines():
            try:
                tables.append(result.split('|')[1].strip())
            except IndexError:
                pass

        os.unlink(self.tmp.name)

        return tables

    def descTable(self, tableName):
        query = self.settings['queries']['desc table']['query'] % tableName
        command = self._getCommand(self.settings['queries']['desc table']['options'], query)
        command.show()

        os.unlink(self.tmp.name)

    def showTableRecords(self, tableName):
        query = self.settings['queries']['show records']['query'] % tableName
        command = self._getCommand(self.settings['queries']['show records']['options'], query)
        command.show()

        os.unlink(self.tmp.name)

class Command:
    def __init__(self, text):
        self.text = text

    def _display(self, panelName, text):
        if not sublime.load_settings("SQLExec.sublime-settings").get('show_result_on_window'):
            panel = sublime.active_window().create_output_panel(panelName)
            sublime.active_window().run_command("show_panel", {"panel": "output." + panelName})
        else:
            panel = sublime.active_window().new_file()
            panel.set_name("SQL Results")

        panel.set_read_only(False)
        panel.set_syntax_file('Packages/SQLExec/SQLResults.tmLanguage')
        panel.set_scratch(True)
        print(panel.settings().get('syntax'))
        panel.run_command('append', {'characters': text})
        panel.set_read_only(True)

    def _result(self, text):
        self._display('SQLExec', text)

    def _errors(self, text):
        self._display('SQLExec.errors', text)

    def run(self):
        sublime.status_message(' SQLExec: running SQL command')
        results, errors = subprocess.Popen(self.text, stdout=subprocess.PIPE,stderr=subprocess.PIPE, shell=True).communicate()

        if not results and errors:
            self._errors(errors.decode('utf-8', 'replace').replace('\r', ''))

        return results.decode('utf-8', 'replace').replace('\r', '')

    def show(self):
        results = self.run()

        if results:
            self._result(results)

class Selection:
    def __init__(self, view):
        self.view = view
    def getQueries(self):
        text = []
        if self.view.sel():
            for region in self.view.sel():
                if region.empty():
                    text.append(self.view.substr(self.view.line(region)))
                else:
                    text.append(self.view.substr(region))
        return text

class Options:
    def __init__(self, name):
        self.name     = name
        connections   = sublime.load_settings("SQLExec.sublime-settings").get('connections')
        self.type     = connections[self.name]['type']
        self.host     = connections[self.name]['host']
        self.port     = connections[self.name]['port']
        self.username = connections[self.name]['username']
        self.password = connections[self.name]['password']
        self.database = connections[self.name]['database']
        if 'service' in connections[self.name]:
            self.service  = connections[self.name]['service']

    def __str__(self):
        return self.name

    @staticmethod
    def list():
        names = []
        connections = sublime.load_settings("SQLExec.sublime-settings").get('connections')
        for connection in connections:
            names.append(connection)
        names.sort()
        return names


def sqlChangeConnection(index):
    global connection
    names = Options.list()
    options = Options(names[index])
    connection = Connection(options)
    sublime.status_message(' SQLExec: switched to %s' % names[index])

def showTableRecords(index):
    global connection
    if index > -1:
        if connection != None:
            tables = connection.desc()
            connection.showTableRecords(tables[index])
        else:
            sublime.error_message('No active connection')

def descTable(index):
    global connection
    if index > -1:
        if connection != None:
            tables = connection.desc()
            connection.descTable(tables[index])
        else:
            sublime.error_message('No active connection')

def executeHistoryQuery(index):
    global history
    if index > -1:
        executeQuery(history[index])

def executeQuery(query):
    global connection
    global history
    history.append(query)
    if connection != None:
        connection.execute(query)


class sqlHistory(sublime_plugin.WindowCommand):
    global history
    def run(self):
        sublime.active_window().show_quick_panel(history, executeHistoryQuery)


class sqlDesc(sublime_plugin.WindowCommand):
    def run(self):
        global connection
        if connection != None:
            tables = connection.desc()
            sublime.active_window().show_quick_panel(tables, descTable)
        else:
            sublime.error_message('No active connection')


class sqlShowRecords(sublime_plugin.WindowCommand):
    def run(self):
        global connection
        if connection != None:
            tables = connection.desc()
            sublime.active_window().show_quick_panel(tables, showTableRecords)
        else:
            sublime.error_message('No active connection')


class sqlQuery(sublime_plugin.WindowCommand):
    def run(self):
        global connection
        global history
        if connection != None:
            sublime.active_window().show_input_panel('Enter query', history[-1], executeQuery, None, None)
        else:
            sublime.error_message('No active connection')


class sqlExecute(sublime_plugin.WindowCommand):
    def run(self):
        global connection
        if connection != None:
            selection = Selection(self.window.active_view())
            connection.execute(selection.getQueries())
        else:
            sublime.error_message('No active connection')


class sqlListConnection(sublime_plugin.WindowCommand):
    def run(self):
        sublime.active_window().show_quick_panel(Options.list(), sqlChangeConnection)


class sqlPad(sublime_plugin.WindowCommand):
    def run(self):
        global connection
        pad = sublime.active_window().new_file()
        pad.set_name("SQL Pad")
        pad.set_syntax_file('Packages/SQLExec/SQLExec.hidden-tmLanguage')
        pad.settings().set('color_scheme','Packages/SQLExec/color_schemes/base16-tomorrow.dark.tmTheme')
        pad.set_scratch(True)

        if connection == None:
            sublime.active_window().run_command("sql_list_connection")


class SQLAutoComplete(sublime_plugin.EventListener):

    # This will return all words found in the dictionary.
    def get_autocomplete_list(self, word):
        global connection
        if connection != None:
            self.word_list = connection.desc()
            # print(self.word_list)
        autocomplete_list = []
        # filter relevant items:
        for w in self.word_list:
            try:
                if word.lower() in w.lower():
                    if len(word) > 0 and word[0].isupper():
                        W = w.title()
                        autocomplete_list.append((W, W))
                    else:
                        autocomplete_list.append((w, w))
            except UnicodeDecodeError:
                print(w)
                continue
        return autocomplete_list

    # gets called when auto-completion pops up.
    def on_query_completions(self, view, prefix, locations):
        if view.match_selector(locations[0], "source.sql"):
            return self.get_autocomplete_list(prefix)


class sqlExecQuickPanel(sublime_plugin.WindowCommand):
    def run(self):
        items = ['Execute', 'History...', 'Desc Table...', 'Show Table Records...', 'List Connections...']
        sublime.active_window().show_quick_panel(items, self.executeCommnad)

    def executeCommnad(self, index):
        commands = ['sql_execute', 'sql_history', 'sql_desc', 'sql_show_records', 'sql_list_connection']
        sublime.set_timeout(lambda: sublime.active_window().run_command(commands[index]), 10)

