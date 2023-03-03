import argparse
import pathlib
import random
import shutil
import tkinter
from tkinter import ttk, filedialog
import threading

ROOT = pathlib.Path(__file__).parent
DEFAULTEXT = []

def default_pipe(info):
    if info.get("type") == "end": return
    elif info.get("type") == "gatherdirectory":
        print(f"Searching: {info.get('directory')}")
    elif info.get("type") == "gather":
        print(f"Found: {info.get('file')}")
    elif info.get("type") == "move":
        print(f"\tMoving {info.get('file').relative_to(info.get('source'))} -> {info.get('newpath').relative_to(info.get('target'))}")

def gather_files(source, ext, recurse, pipe = default_pipe):
    files = []
    def parse_dir(dir):
        pipe({"type": "gatherdirectory", "directory":dir})
        for file in dir.iterdir():
            if not file.is_file():
                if file.is_dir() and recurse:
                    parse_dir(file)
                continue
            if ext and not file.suffix in ext: continue
            pipe({"type":"gather", "directory":dir, "file":file})
            files.append(file)

    if not isinstance(source, pathlib.Path):
        source = pathlib.Path(source).resolve()

    parse_dir(source)

    pipe({"type":"end", "result":files})
    return files
    
def move_files(files, source, target, pipe = default_pipe):
    try:
        output = []

        if not files: return pipe({"type":"end", "result":None})

        if not isinstance(source, pathlib.Path):
            source = pathlib.Path(source).resolve()

        if not isinstance(target, pathlib.Path):
            target = pathlib.Path(target).resolve()

        random.shuffle(files)
        total = len(files)
        for i,file in enumerate(files):
            newname = file.with_stem(f"{i} - {file.stem}").name
            newpath = (target / newname).resolve()
            pipe({"type":"move","file":file, "newpath":newpath, "source":source, "target":target, "remaining":total-i-1, "total":total})
            shutil.copy2(file, newpath)
            output.append([file, newpath])

        pipe({"type":"end", "result":output})
        return output
    except Exception as e:
        pipe({"type": "error", "error": e})
        raise e

class ProgressWindow(tkinter.Toplevel):
    def __init__(self, parent, onexit = None, takefocus = True, **kw):
        super().__init__(takefocus=takefocus, **kw)
        self.parent = parent
        self.onexit = onexit
        self.result = None
        self.update_idletasks()
        self.overrideredirect(True)

        self.status = ttk.Label(self)
        self.progressvar = tkinter.IntVar()
        self.progressvar.set(0)
        self.progress = ttk.Progressbar(self, variable= self.progressvar)
        for child in self.winfo_children(): child.pack()

    def update(self, info):
        if info.get("type") == "end":
            self.result = info.get("result")
            self.setend()
        
        elif info.get("type") == "error":
            print(info.get("error"))
            self.destroy()
        
        elif info.get("type") == "gatherdirectory":
            self.status.configure(text = f"{info.get('directory')}:")
        elif info.get("type") == "gather":
            self.status.configure(text = f"{info.get('directory')}: {info.get('file')}")
        elif info.get("type") == "move":
            self.status.configure(text = f"Moving {info.get('file').relative_to(info.get('source'))} -> {info.get('newpath').relative_to(info.get('target'))}")
            [total, remaining] = info.get("total"), info.get("remaining")
            self.progressvar.set(int((total-remaining) / total * 100))
            self.update_idletasks()
    
    def setend(self):
        self.progressvar.set(100)
        self.status.configure(text = "Done")
        self.after(1000, lambda: self.destroy())

    def destroy(self):
        super().destroy()
        if self.onexit:
            self.onexit(self.result)


class GUI(tkinter.Frame):
    def __init__(self, master, *args, **kw) -> None:
        super().__init__(master, *args, **kw)
        self.root = master

        ttk.Label(self, text = "File Transfer Shuffler", font=("Times", 18, "bold"))
        ttk.Label(self, text="Locates Files in one Folder and Transfers it to another Folder in a Random Order", font=("Times", 12, "italic"))

        boldfont =("times", 12, "bold")
        body = ttk.Frame(self)

        ########## Source ##########
        sourcegrid = ttk.LabelFrame(body, text="Source")

        ## first row
        ttk.Label(sourcegrid, text="Source Location", font=boldfont).grid(row = 0, column = 0)
        self.sourcebutton = ttk.Button(sourcegrid, text="...", command=lambda: self.getDirectory(self.sourceentry, "source"))
        self.sourcebutton.grid(row = 0, column = 1)
        self.sourceentry = ttk.Entry(sourcegrid)
        self.sourceentry.state(["disabled"])
        self.sourceentry.grid(row = 0, column = 2)
        
        ## Second row
        mf = ttk.LabelFrame(sourcegrid, text = "Extensions")
        mf.grid(row = 1, column = 0, columnspan = 3)

        f = ttk.Frame(mf)
        self.deleteextbutton = ttk.Button(f, text="Delete", command = self.deleteext)
        self.deleteextbutton.pack(side='top', fill='x')
        self.extensions = tkinter.Listbox(f)
        self.extensions.pack(side = 'left', fill = 'y', expand = True)
        self.extensions.bind("<Delete>", self.deleteext)
        self.extensions.bind("<Button-3>", self.rightdeleteext)
        s = tkinter.Scrollbar(f, command = self.extensions.yview)
        s.pack(side = 'right', fill = 'y')
        self.extensions.configure(yscrollcommand=s.set)

        self.extentry = ttk.Entry(mf)
        self.extentry.bind("<Return>", lambda *e: self.addextension())
        
        self.extaddbutton = ttk.Button(mf, text = "Add Ext", command = self.addextension)

        for child in mf.winfo_children():
            child.pack(side='left', anchor ='s')

        
        ## Third Row
        self.recursevar = tkinter.BooleanVar()
        self.recursevar.set(True)
        self.recursecheckbox = ttk.Checkbutton(sourcegrid, text="Recurse Directory", variable=self.recursevar)
        self.recursecheckbox.grid(row =2, column = 0)

        ########## Target ##########
        targetgrid = ttk.LabelFrame(body, text="Target")

        ## First Row
        ttk.Label(targetgrid, text="Target Location", font=boldfont).grid(row = 0, column = 0)
        self.targetbutton = ttk.Button(targetgrid, text="...", command=lambda: self.getDirectory(self.targetentry, "target"))
        self.targetbutton.grid(row = 0, column = 1)
        self.targetentry = ttk.Entry(targetgrid)
        self.targetentry.state(["disabled"])
        self.targetentry.grid(row = 0, column = 2)


        for child in body.winfo_children():
            child.pack(side='left', fill='y', expand=True)

        self.randombutton = ttk.Button(self, text = "Begin Randomization", command = self.randomize)

        for child in self.winfo_children():
            child.pack()

    def getDirectory(self, entry, key):
        result = filedialog.askdirectory(mustexist=True)
        if not result: return
        entry.state(["!disabled"])
        entry.delete(0,'end')
        entry.insert(0,result)
        entry.xview("end")
        entry.state(["disabled"])

    def deleteext(self, *e):
        sel = self.extensions.curselection()
        if not sel: return
        self.extensions.delete(sel[0])

    def rightdeleteext(self, event):
        nearest = self.extensions.nearest(event.y)
        if nearest < 0: return
        bbox = self.extensions.bbox(nearest)
        if event.y < bbox[1] or event.y > bbox[1]+bbox[3]: return
        self.extensions.delete(nearest)

    def addextension(self):
        result = self.extentry.get().strip()
        if not result: return
        self.extentry.delete(0, 'end')
        self.extensions.insert('end', result)

    def randomize(self):
        def recurseDisable(widget):
            for child in widget.winfo_children():
                try:
                    child.state(["disabled"])
                except: pass
                if hasattr(child, "winfo_children") and child.winfo_children():
                    recurseDisable(child)

        recurseDisable(self)

        self.source = self.sourceentry.get()
        self.target = self.targetentry.get()
        self.extensions = self.extensions.get(0,'end')
        self.recursive = self.recursevar.get()

        p = ProgressWindow(self, onexit = self.movefiles)

        self.backgroundthread = threading.Thread(target=gather_files,
                                                 kwargs=dict(source= self.source, ext= self.extensions, recurse= self.recursive, pipe = p.update),
                                                 daemon=True)
        self.backgroundthread.start()

    def movefiles(self, result):
        self.backgroundthread.join()
        self.files = result

        if not self.files: return self.root.destroy()

        p = ProgressWindow(self, onexit= lambda *e, **ev: self.root.destroy())
        t = threading.Thread(target = move_files,
                             kwargs=dict(files=self.files, source=self.source, target=self.target, subtarget=False, pipe=p.update ),
                             daemon=True)
        t.start()


def cli_main():
    parser = argparse.ArgumentParser(
        prog = "File Transfer Shuffler",
        description= """Copies and Renames files from one folder to another folder""",
    )
    subparser = parser.add_subparsers(help="File Transfer Shuffler provides Commandline and Graphical interfaces via cli and gui respectively")

    cliparser = subparser.add_parser("cli", help="Use Commandline Arguments")
    cliparser.set_defaults(mode="cli")
    cliparser.add_argument("-t", "--target", required=True, help="The Folder to add the files to")
    cliparser.add_argument("-s", "--source", required=False, help="The Source Folder of the files")
    cliparser.add_argument("-x", "--source-ext", nargs="*", required=False, help="Specifies what File Types to scan for in the Source Folder")
    cliparser.add_argument("-nr", "--no-recurse", action="store_false", required=False, help="Don't recursively search all subfolders of the Source Folder")

    tkinterparser = subparser.add_parser("gui", help="Initialize GUI Input")
    tkinterparser.set_defaults(mode="gui")
    
    args = vars(parser.parse_args())

    if args.get("mode") == "cli":
        return cli(args)
    
    return gui(args)

def cli(args):
    try:
        rawtarget = args.get("target")
        target = pathlib.Path(rawtarget).resolve()
        assert target.exists()
    except:
        print(f"Invalid Target: {rawtarget}")

    try:
        rawsource = args.get("source")
        if rawsource:
            source = pathlib.Path(rawsource).resolve()
            assert source.exists()
    except:
        print(f"Invalid Source: {rawsource}")

    ext = []
    rawext = args.get("source_ext")
    if(rawext):
        for x in rawext:
            if not x.startswith("."):
                x = "."+x
            ext.append(x)

    recurse = args.get("no_recurse")

    files = gather_files(source=source, ext=ext, recurse=recurse)

    move_files(files= files, source= source, target=target)

    print("Done")

def gui(args):
    root = tkinter.Tk()
    root.title("File Transfer Shuffler")
    GUI(root).pack(padx=3, pady=3, fill='both', expand = True)
    root.mainloop()


if __name__ == "__main__":
    cli_main()


