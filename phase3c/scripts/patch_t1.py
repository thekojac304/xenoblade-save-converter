p = r"C:\Dev\XC_Wii_to_DE_Research\phase3c\tests\test_phase3c_metadata.py"
s = open(p, encoding="utf-8").read()
a = s.index("        r1 = s3.convert3(s3.ThreeDSRequest(\"wii_to_3ds\"")
b = s.index("        x = s3.load_3ds(r1.main_output")
s = s[:a] + '''        r1 = s3.convert3(s3.ThreeDSRequest("wii_to_3ds", source=self.exp.main_output, out=os.path.join(d, "x"),
                                           template=H.X3_USER))
''' + s[b:]
s = s.replace('''        w = F.make_newest(w, "weapon", ws) if False else w
''', "")
a = s.index("        b3 = rd(subprocess.run(")
b = s.index("        self.assertEqual(shared(b3), shared(back))")
s = s[:a] + '''        r = subprocess.run([sys.executable, BASELINE, "convert3", json.dumps(dict(
            direction="3ds_to_de", source=p, out=os.path.join(d, "b3b"), record=r1.sidecar_path,
            current=H.DE_S232))], capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        b3 = rd(json.loads(r.stdout.strip().splitlines()[-1])["main_output"])
''' + s[b:]
open(p, "w", encoding="utf-8").write(s)
