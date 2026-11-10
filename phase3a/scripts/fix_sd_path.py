p = r"C:\Dev\XC_Wii_to_DE_Research\RELEASE_READINESS.md"
s = open(p, encoding="utf-8").read()
s = s.replace("SD:\x03ds\\Checkpoint", "SD:\\3ds\\Checkpoint")
open(p, "w", encoding="utf-8").write(s)
print("\x03" in s, s.count("SD:\\3ds\\Checkpoint"))
