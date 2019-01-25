import os
import sys
import time
import tkinter as tk
import tkinter.ttk as ttk
from threading import Thread
from PyCRC.CRC16 import CRC16
from typing import List

from intelhex import IntelHex
import tkinter.filedialog as filedialog
try:
    Spinbox = ttk.Spinbox
except AttributeError:
    Spinbox = tk.Spinbox

APPNAME = "Hex2Efa"
BLOCK_WIDTH = 16
BLOCK_HEIGHT = 32
BLOCK_SIZE = 124 # 124 bytes
ENCODINGS = ("ASCII", "CP037", "CP850", "CP1140", "CP1252",
             "Latin1", "ISO8859_15", "Mac_Roman", "UTF-8",
             "UTF-8-sig", "UTF-16", "UTF-32")


class MainWindow:

    def __init__(self, parent):
        self.filename = None
        self.parent = parent
        self.size = 0
        self.version = []
        self.progress_index = 0
        self.progress_index_text = tk.IntVar()
        self.progress_index_text.set(self.progress_index)
        self.success = ""
        self.success_text = tk.StringVar()
        self.success_text.set(self.success)
        self.create_widgets()
        self.create_layout()
        self.create_bindings()

        if len(sys.argv) > 1:
            self._open(sys.argv[1])

    def make_form(self):
        entries = []
        fields = [1, 2, 3, 4]
        for field in fields:
            ent = ttk.Entry(self.entsFrame, width=4)
            ent.grid(row=0, column=field)
            entries.append(ent)
        return entries

    def create_widgets(self):
        ttk.Style().configure("C.TButton", padding=6, background="#ccc")
        frame = self.frame = ttk.Frame(self.parent)
        self.openButton = ttk.Button(frame, text="Open...", underline=0,
                                     command=self.open, style="C.TButton")
        self.convertButton = ttk.Button(frame, text="Convert", underline=0,
                                        command=self.start_thread, style="C.TButton")
        self.quitButton = ttk.Button(frame, text="Quit", underline=0,
                                     command=self.quit, style="C.TButton")
        self.entsFrame = ttk.Frame(self.parent)
        self.textVersion = ttk.Label(self.entsFrame, text="Enter board version:")
        self.entsVersion = self.make_form()
        self.parent.bind('<Return>', (lambda event, e=self.entsVersion: self.fetch(e)))
        self.entryButton = ttk.Button(self.entsFrame, text="Apply", underline=0,
                                     command=(lambda e=self.entsVersion: self.fetch(e)))
        self.progressBar = ttk.Progressbar(frame, variable=self.progress_index_text, length=200)
        self.progressRow = ttk.Label(frame, text="Progress:")
        self.progressCount = ttk.Label(frame, textvariable=self.progress_index_text)
        self.successText = tk.Label(frame, textvariable=self.success_text)
        self.emptyRow1 = ttk.Label(frame)
        self.emptyRow2 = ttk.Label(frame)
        self.emptyRow3 = ttk.Label(frame)

    def create_layout(self):
        self.frame.grid(row=0, columnspan=3)
        for column, widget in enumerate((
                self.openButton,
                self.convertButton,
                self.quitButton,)):
            widget.grid(row=0, column=column)
        self.emptyRow1.grid(row=1, column=0)
        self.entsFrame.grid(row=0, column=1, sticky='w')
        self.textVersion.grid(row=0, column=0, sticky='w')
        self.entryButton.grid(row=0, column=5)
        self.emptyRow2.grid(row=2, column=0)
        self.emptyRow3.grid(row=3, column=0)
        for column, widget in enumerate((
                self.progressRow,
                self.progressBar,
                self.progressCount,)):
            widget.grid(row=4, column=column)
        self.successText.grid(row=5, column=1)

    def create_bindings(self):
        for keypress in ("<Control-o>", "<Alt-o>"):
            self.parent.bind(keypress, self.open)
        for keypress in ("<Control-q>", "<Alt-q>", "<Escape>"):
            self.parent.bind(keypress, self.quit)

    def open(self, *args):
        filename = filedialog.askopenfilename(title="Open — {}".format(
                                              APPNAME))
        self._open(filename)

    def _open(self, filename):
        if filename and os.path.exists(filename):
            self.parent.title("{} — {}".format(filename, APPNAME))
            self.size = os.path.getsize(filename)
            self.filename = filename
            if self.success:
                self.version = []
                for ent in self.entsVersion:
                    ent.configure(state="normal")
                    ent.delete(0, 'end')
                self.progress_index = 0
                self.progress_index_text.set(self.progress_index)
                self.success = ""
                self.success_text.set(self.success)

    def convert(self, *args):
        if not self.filename or not self.version:
            return
        ih = IntelHex(self.filename)
        block_num = [0x00, 0x00]
        arr = ih.tobinarray() # массив с "голыми" данными из hex-файла
        arr = bytes(arr)
        # Необходимо записать данные в файл. строка = 16 байт
        # Заголовок: строка 1 - E F A m e d i c a L L C _ _ _ _ (версия железа)
        # строка 2 - размер прошивки (4 байта) + crc16(2 байта) + padding(8 байт,ljust) + crc16 заголовка (2 бвйтв)
        header = self.get_header()
        #print([int(i) for i in header])

        # Далее блоки. Блок - 128 байт:
        # № блока (2 байта) + прошивка (124 байта), + CRC16 (2 байта)
        fout = open('bintest.efa', 'wb')
        fout.write(header) # Сначала записываем заголовок
        for block in range(0, len(arr), BLOCK_SIZE):
            # Номер блока
            arr_for_crc = bytes(block_num) + arr[block:block + BLOCK_SIZE]
            if(block_num[1] <= 255):
                block_num[1] += 1
            else: # предполагается, что блоков будет точно меньше 65535
                block_num[1] = 1
                block_num[0] += 1
            arr_with_crc = arr_for_crc + CRC16().calculate(arr_for_crc).to_bytes(2, byteorder='big')
            fout.write(arr_with_crc)
            self.get_progress(len(arr), block)
        fout.close()
        self.get_success()

        # TEST
        fout = open('bintest.efa', 'rb')
        #print([int(i) for i in fout.read()])
        fout.close()

    def start_thread(self):
        self.t = Thread(target=self.convert)
        self.t.start()

    def fetch(self, entries):
        for entry in entries:
            text = entry.get()
            self.version.append(text)
            entry.configure(state="readonly")

    def get_header(self):
        ver = self.version
        version = bytes()
        for sym in ver:
            if sym.isdigit():
                version += int(sym).to_bytes(1, byteorder='big')
            else:
                version += str.encode(sym, 'ascii')
        # print(ver, [int(i) for i in version])
        head = 'EFAmedicaLLC'
        head = str.encode(head, 'ascii')
        size_with_crc = (self.size).to_bytes(4, byteorder='big') + \
                        CRC16().calculate(str(self.size)).to_bytes(2, byteorder='big')
        padding = bytes([0, 0, 0, 0, 0, 0, 0, 0])
        head_for_crc = head + version + size_with_crc + padding
        head_with_crc = head_for_crc + CRC16().calculate(head_for_crc).to_bytes(2, byteorder='big')
        return head_with_crc

    def get_progress(self, total, current):
        if total - current <= BLOCK_SIZE:
            self.progress_index = 100
        else:
            self.progress_index = int(current / total * 100)
        time.sleep(0.01)  # для красоты, можно убрать
        self.progress_index_text.set(self.progress_index)

    def get_success(self):
        self.success = "Success!"
        self.success_text.set(self.success)

    def quit(self, event=None):
        self.parent.destroy()


app = tk.Tk()
app.title(APPNAME)
window = MainWindow(app)
app.protocol("WM_DELETE_WINDOW", window.quit)
app.resizable(width=False, height=False)
app.geometry('{}x{}'.format(372, 150))
app.mainloop()