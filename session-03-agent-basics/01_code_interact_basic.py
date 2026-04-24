"""
Session 3 - Demo 1: code.interact() basics
Run this and interact with the shell to inspect variables.
Exit with Ctrl+D to continue, or exit() to terminate.
"""
import code

x = 42
y = "Hello TSAI"
z = [1, 2, 3, 4, 5]

print("Variables defined: x, y, z")
print("Dropping into interactive shell...")
print("Try typing: x, y, z, type(x), len(z)")
print("Exit with Ctrl+D to continue, exit() to stop\n")

# Drop into interactive shell
code.interact(local=locals())

print("\nYou continued! This line runs because you used Ctrl+D.")
print(f"x is still {x}, y is still {y}")
