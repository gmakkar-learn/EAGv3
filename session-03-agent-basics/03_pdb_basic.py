"""
Session 3 - Demo 3: pdb basics
Run this and use pdb commands:
  p x    - print x
  p y    - print y
  s      - step into the add() function
  n      - next line (don't step into functions)
  c      - continue execution
  b 11   - set breakpoint at line 11
  q      - quit
"""

def add(a, b):
    result = a + b
    return result

x = 5
y = 15
breakpoint()  # Modern way (Python 3.7+) — same as: from pdb import set_trace; set_trace()

z = add(x, y)
print("Result:", z)
