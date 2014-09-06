
import sublime, sublime_plugin
import os, re

####
#### Removing
def erase_region(view, edit, region):
	view.erase(edit, region)
	return region.begin()

def remove_spaces(view, edit, point, remove_newlines=True, erase_left=True, erase_right=True):
	left_limit = None
	right_limit = None

	def isspace(c):
		if remove_newlines:
			return c.isspace()
		return c == " "

	if not erase_left:
		left_limit = point
	elif (point - 1 >= 0 and
	    is_inside_word(view.substr(point - 1))):
		left_limit = point
	else:
		for (i, c) in walk_left(view, point - 1):
			if not isspace(c):
				left_limit = i + 1
				break

	if not erase_right:
		right_limit = point
	elif is_inside_word(view.substr(point)):
		right_limit = point
	else:
		for (i, c) in walk_right(view, point):
			if not isspace(c):
				right_limit = i
				break

	if left_limit and right_limit and left_limit != right_limit:
		view.erase(edit, sublime.Region(left_limit, right_limit))
	return left_limit

####
#### Context checking
def is_point_inside_regions(point, regions):
	for region in regions:
		if point > region.begin() and point < region.end():
			return region

def is_inside_string(view, point):
	if view.score_selector(point, "string") > 0:
		return is_point_inside_regions(point, view.find_by_selector("string"))

def is_inside_comment(view, point):
	test_point = point
	if (point == view.size() and point - 1 >= 0 and
	    view.substr(point - 1) != "\n"):
		test_point = point - 1
	if view.score_selector(test_point, "comment") > 0:
		return view.extract_scope(test_point)

whitespace_matcher = re.compile("\s*$")
def is_expression_empty(string):
	return whitespace_matcher.match(string[1:-1])

def is_inside_word(c):
	return not (c.isspace() or char_type(c))

####
#### Get expression
def find_enclosing_brackets(view, point, left_bracket, right_bracket):
	left_parens = None
	right_parens = None

	i = point - 1
	parens_count = 0
	while i >= 0:
		c = view.substr(i)
		if c == left_bracket:
			parens_count += 1
		elif c == right_bracket:
			parens_count -= 1

		if parens_count == 1:
			left_parens = i
			break
		i -= 1

	i = point
	parens_count = 0
	end = view.size()
	while i < end:
		c = view.substr(i)
		if c == left_bracket:
			parens_count += 1
		elif c == right_bracket:
			parens_count -= 1

		if parens_count == -1:
			right_parens = i + 1
			break
		i += 1

	return (left_parens, right_parens)

def max_with_none(*args):
	out = args[0]

	for arg in args:
		if arg:
			if not out or (out and arg > out):
				out = arg

	return out

def get_expression(view, point, direction="forward"):
	string_region = is_inside_string(view, point)
	if string_region:
		if direction == "forward":
			return (string_region.begin(), string_region.end())
		else:
			return (string_region.end(), string_region.begin())

	paren = (lparen, rparen) = find_enclosing_brackets(view, point, "(", ")")
	brack = (lbrack, rbrack) = find_enclosing_brackets(view, point, "[", "]")
	curly = (lcurly, rcurly) = find_enclosing_brackets(view, point, "{", "}")

	m = max_with_none(lparen, lbrack, lcurly)

	out = None
	if   m == lparen: out = paren
	elif m == lbrack: out = brack
	elif m == lcurly: out = curly

	if out:
		if direction == "backward":
			return tuple(reversed(out))
		return out

	return (None, None)

def get_next_expression(view, point, skip_endbrackets=False, direction="forward", skip_words=False):
	if direction == "backward":
		return tuple(reversed(get_previous_expression(view, point, skip_endbrackets, skip_words)))

	for (i, c) in walk_right(view, point):
		if not c.isspace():
			if (not skip_words) and is_inside_word(c):
				return get_word(view, i)
			t = char_type(c)
			if t == "lbracket" or t == "string":
				return get_expression(view, i + 1)
			elif (not skip_endbrackets) and t == "rbracket":
				return (None, None)

	return (None, None)

def get_previous_expression(view, point, skip_endbrackets=False, skip_words=False):
	for (i, c) in walk_left(view, point):
		if not c.isspace():
			if (not skip_words) and is_inside_word(c):
				return get_word(view, i)
			t = char_type(c)
			if t == "rbracket" or t == "string":
				return get_expression(view, i)
			elif (not skip_endbrackets) and t == "lbracket":
				return (None, None)

	return (None, None)

def get_word(view, point, direction="forward"):
	word_left = None
	word_right = None

	if not is_inside_word(view.substr(point)):
		return (None, None)

	for (i, c) in walk_left(view, point):
		if not is_inside_word(c):
			word_left = i + 1
			break

	for (i, c) in walk_right(view, point):
		if not is_inside_word(c):
			word_right = i
			break

	word_left = word_left or 0
	word_right = word_right or view.size()

	if direction == "backward":
		return (word_right, word_left)
	return (word_left, word_right)

def get_next_word(view, point):
	word_start = None

	for (i, c) in walk_right(view, point):
		if is_inside_word(c):
			if not word_start:
				word_start = i
		elif word_start:
			return (word_start, i)

	return (word_start, view.size())

def get_previous_word(view, point):
	word_end = None

	for (i, c) in walk_left(view, point - 1):
		if is_inside_word(c):
			if not word_end:
				word_end = i + 1
		elif word_end:
			return (i + 1, word_end)

	return (0, word_end)

def bracket_count(text, left_bracket, right_bracket, return_on_right_bracket=True):
	count = 0
	for c in text:
		if c == left_bracket:
			count += 1
		elif c == right_bracket:
			count -= 1
		if return_on_right_bracket and count < 0:
			return count
	return count

####
#### Get character
def get_next_character(view, point):
	for (i, c) in walk_right(view, point):
		if not c.isspace():
			return (i, c)
	return (None, None)

def get_previous_character(view, point):
	for (i, c) in walk_left(view, point):
		if not c.isspace():
			return (i, c)
	return (None, None)

####
#### Misc
def edit_selections(view, f):
	new_regions = []

	for i in range(len(view.sel())):
		region = view.sel()[i]
		new_region = f(region)
		new_regions += [new_region]

	view.sel().clear()
	for region in new_regions:
		if not region == None:
			view.sel().add(region)

def char_type(c):
	if c == "\"": return "string"
	elif c == "(" or c == "[" or c == "{": return "lbracket"
	elif c == ")" or c == "]" or c == "}": return "rbracket"

def step(i, steps, direction):
	if direction == "forward":
		return i + steps
	elif direction == "backward":
		return i - steps
	else:
		raise Exception("direction must be one of \"forward\" or \"backward\"")

def get_char(view, i, direction):
	if direction == "backward":
		i -= 1
	return view.substr(i)

def insert(view, edit, i, text, direction):
	if direction == "backward":
		i -= 1

	return view.insert(edit, i, text)

def opposite_direction(direction):
	if direction == "forward":
		return "backward"
	if direction == "backward":
		return "forward"

def truthy(*vals):
	for val in vals:
		if (val is False) or (val is None):
			return False

	return True

####
#### Walking
def walk_left(view, point):
	i = point

	while i >= 0:
		c = view.substr(i)
		yield (i, c)
		i -= 1

def walk_right(view, point):
	i = point

	while i < view.size():
		c = view.substr(i)
		yield (i, c)
		i += 1

def walk(view, point, direction):
	if direction == "forward":
		return walk_right(view, point)
	elif direction == "backward":
		return walk_left(view, point)

####
#### Configuration
settings = None

def create_missing_paredit_dir():
	p = os.path.join(sublime.packages_path(), "paredit")
	if not os.path.isdir(p):
		os.makedirs(p)

settings_has_init = False
def init_settings():
	global settings_has_init
	global settings
	if not settings_has_init:
		create_missing_paredit_dir()
		settings = sublime.load_settings("paredit.sublime-settings")
		settings_has_init = True

def is_strict_mode():
	init_settings()
	return settings.get("strict_mode", True)

def is_enabled():
	init_settings()
	return settings.get("enabled", True)

def set_enabled(enabled):
	init_settings()
	settings.set("enabled", enabled)

def check_regexes(regexes, string):
	for regex in regexes:
		if re.search(regex, string):
			return True

def is_correct_syntax(view):
	init_settings()
	syntax_regexes = settings.get("syntax", ["."])
	return check_regexes(syntax_regexes, view.settings().get("syntax"))

def is_correct_file_ending(view):
	init_settings()
	file_ending_regexes = settings.get("file_name", ["."])
	return check_regexes(file_ending_regexes, view.file_name())

def should_paredit(view):
	return (is_enabled() and
	        (is_correct_syntax(view) or
	         is_correct_file_ending(view)))

class PareditListenerCommand(sublime_plugin.EventListener):
	def on_query_context(self, view, key, operator, operand, match_all):
		if key == "should_paredit":
			return should_paredit(view)

class Paredit_toggle_enableCommand(sublime_plugin.ApplicationCommand):
	def run(self):
		set_enabled(not is_enabled())

	def is_checked(self):
		return is_enabled()
