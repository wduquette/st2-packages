
import sublime, sublime_plugin
try:
	from paredit import shared
except:
	import shared

def strict_delete_selection(view, edit, region):
	replace_char = str(chr(1))

	offset = region.begin()
	out = list(view.substr(region))
	point = region.begin()
	while point < region.end():
		if (shared.is_inside_comment(view, point) or
		    shared.is_inside_string(view, point)):
			out[point - offset] = replace_char
			point += 1
			continue

		(a, b) = shared.get_next_expression(view, point, True)
		if shared.truthy(a, b):
			if shared.is_inside_word(view.substr(a)):
				if a > region.end():
					break
				a = max(a, region.begin())
				b = min(b, region.end())
			if b > region.end():
				break
			if not a < region.begin():
				a_local = a - offset
				b_local = b - offset
				out[a_local:b_local] = list(replace_char * (b - a))
			point = b
		else:
			break

	out = "".join(out)
	out = out.replace(replace_char, "").strip()
	view.replace(edit, region, out)

	return region.begin()

def remove_empty_expression(view, edit, point, fail_direction):
	(lb, rb) = shared.get_expression(view, point)

	if shared.truthy(lb, rb):
		expr_region = sublime.Region(lb, rb)
		expression = view.substr(expr_region)
		if shared.is_expression_empty(expression):
			return shared.erase_region(view, edit, expr_region)
		else:
			return sublime.Region(point + fail_direction, point + fail_direction)
	else:
		return point

def standard_delete(view, edit, point, is_forward):
	if is_forward:
		view.erase(edit, sublime.Region(point, point + 1))
		return point
	else:
		view.erase(edit, sublime.Region(point - 1, point))
		return max(0, point - 1)

def paredit_delete(view, edit, is_forward):
	def f(region):
		if not region.begin() == region.end():
			if shared.is_strict_mode():
				return strict_delete_selection(view, edit, region)
			else:
				return shared.erase_region(view, edit, region)

		point = region.begin()

		if is_forward:
			direction = 1
			next_char = view.substr(point)
			skip_char_type = "lbracket"
		else:
			direction = -1
			next_char = view.substr(point - 1)
			skip_char_type = "rbracket"

		next_char_type = shared.char_type(next_char)

		if shared.is_inside_comment(view, point):
			pass # pass to else below
		elif next_char_type == "string":
			if shared.is_inside_string(view, point):
				if ((not is_forward) and
				    (point - 2 >= 0) and
				    view.substr(point - 2) == "\\"):
					return shared.erase_region(view, edit, sublime.Region(point, point - 2))
				else:
					return remove_empty_expression(view, edit, point, direction)
			else:
				return region.begin() + direction
		elif shared.is_inside_string(view, point):
			# Same purpose as is_inside_comment above
			# but has to be tested after the elif above.
			if (is_forward and
			    (point + 2 < view.size()) and
			    view.substr(sublime.Region(point, point + 2)) == "\\\""):
				return shared.erase_region(
					view, edit, sublime.Region(point, point + 2))
			else:
				pass
		elif next_char_type == skip_char_type: return region.begin() + direction
		elif next_char_type:
			return remove_empty_expression(view, edit, point, direction)

		# else
		return standard_delete(view, edit, point, is_forward)

	shared.edit_selections(view, f)

def paredit_forward_delete(view, edit):
	paredit_delete(view, edit, True)

def paredit_backward_delete(view, edit):
	paredit_delete(view, edit, False)

def paredit_kill_abstract(view, edit, expression):
	def f(region):
		if not region.a == region.b:
			return shared.erase_region(view, edit, region)

		point = region.a

		(lb, rb) = shared.get_expression(view, point)
		if shared.truthy(lb, rb):
			region = sublime.Region(lb, rb)
			if shared.is_expression_empty(view.substr(region)):
				shared.erase_region(view, edit, region)
				return lb
			elif expression:
				view.erase(edit, sublime.Region(lb + 1, rb - 1))
				return lb + 1
			else:
				view.erase(edit, sublime.Region(point, rb - 1))
				return point
		else:
			line_region = view.line(point)
			a = line_region.begin()
			if not expression:
				a = point
			return shared.erase_region(view, edit, sublime.Region(a, line_region.end()))

	shared.edit_selections(view, f)

def paredit_kill(view, edit):
	paredit_kill_abstract(view, edit, False)

def paredit_kill_expression(view, edit):
	paredit_kill_abstract(view, edit, True)

def paredit_kill_word(view, edit, is_forward):
	def f(region):
		if not region.a == region.b:
			return region
		point = region.a

		if is_forward:
			(lw, rw) = shared.get_next_word(view, point)
		else:
			(lw, rw) = shared.get_previous_word(view, point)

		if shared.truthy(lw, rw):
			return shared.erase_region(view, edit, sublime.Region(lw, rw))

		return region

	shared.edit_selections(view, f)

def paredit_forward_kill_word(view, edit):
	paredit_kill_word(view, edit, True)

def paredit_backward_kill_word(view, edit):
	paredit_kill_word(view, edit, False)

####
#### Commands
class Paredit_forward_deleteCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		paredit_forward_delete(self.view, edit)

class Paredit_backward_deleteCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		paredit_backward_delete(self.view, edit)

class Paredit_killCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		paredit_kill(self.view, edit)

class Paredit_kill_expressionCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		paredit_kill_expression(self.view, edit)

class Paredit_forward_kill_wordCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		paredit_forward_kill_word(self.view, edit)

class Paredit_backward_kill_wordCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		paredit_backward_kill_word(self.view, edit)
