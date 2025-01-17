import tkinter as tk
from tkinter import ttk, messagebox
import yfinance as yf
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# Farbdefinitionen für das dunkle Theme
BG_COLOR = "#121212"        # Haupt-Hintergrund
SIDEBAR_COLOR = "#1c1c1c"   # Sidebar-Hintergrund
FG_COLOR = "#ffffff"        # Schriftfarbe
ACCENT_COLOR = "#4a90e2"     # Akzentfarbe (z. B. für Buttons)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Aktien & ETF Portfolio")
        self.geometry("1100x650")
        self.configure(bg=BG_COLOR)

        # ttk Style initialisieren und konfigurieren
        style = ttk.Style(self)
        style.theme_use("clam")  # 'clam' ist oft ein guter Ausgangspunkt
        style.configure("TFrame", background=BG_COLOR)
        style.configure("TLabel", background=BG_COLOR, foreground=FG_COLOR, font=("Helvetica", 11))
        style.configure("Header.TLabel", font=("Helvetica", 16, "bold"))
        style.configure("TButton", background=SIDEBAR_COLOR, foreground=FG_COLOR, relief="flat", font=("Helvetica", 10))
        style.map("TButton",
                  background=[("active", ACCENT_COLOR)],
                  foreground=[("active", FG_COLOR)])
        style.configure("TEntry", fieldbackground=SIDEBAR_COLOR, foreground=FG_COLOR, font=("Helvetica", 10))
        style.configure("TCombobox", fieldbackground=SIDEBAR_COLOR, foreground=FG_COLOR, font=("Helvetica", 10))

        # Portfolio-Daten (in Memory, z. B. später in Datei speichern)
        self.portfolio = []

        # Erstelle den Container für Sidebar und Hauptbereich
        self.sidebar = ttk.Frame(self, width=220)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.config(style="TFrame")
        self.sidebar.configure(relief="sunken")

        self.container = ttk.Frame(self)
        self.container.pack(side="right", fill="both", expand=True)

        # Sidebar mit modernisierten Buttons
        self.create_sidebar()

        # Seiten in einem Dictionary verwalten
        self.frames = {}
        for F in (MarketPage, PortfolioPage, OtherPage):
            frame = F(parent=self.container, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("MarketPage")

    def create_sidebar(self):
        # Setze den Hintergrund der Sidebar über ein eigenes Label als Platzhalter
        sidebar_bg = tk.Label(self.sidebar, background=SIDEBAR_COLOR)
        sidebar_bg.place(relwidth=1, relheight=1)

        btn_market = ttk.Button(self.sidebar, text="Aktueller Markt",
                                command=lambda: self.show_frame("MarketPage"))
        btn_market.pack(fill="x", padx=20, pady=(30, 10))

        btn_portfolio = ttk.Button(self.sidebar, text="Portfolio",
                                   command=lambda: self.show_frame("PortfolioPage"))
        btn_portfolio.pack(fill="x", padx=20, pady=10)

        btn_other = ttk.Button(self.sidebar, text="Weitere Menüpunkte",
                               command=lambda: self.show_frame("OtherPage"))
        btn_other.pack(fill="x", padx=20, pady=10)

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()


class MarketPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        # Titel
        lbl_title = ttk.Label(self, text="Aktueller Markt", style="Header.TLabel")
        lbl_title.pack(pady=(20,10))

        # Eingabefeld für Ticker-Symbol (modernisiert mit ttk.Entry)
        ticker_frame = ttk.Frame(self)
        ticker_frame.pack(pady=5)
        ttk.Label(ticker_frame, text="Ticker-Symbol:").pack(side="left", padx=5)
        self.ticker_entry = ttk.Entry(ticker_frame, width=10)
        self.ticker_entry.pack(side="left", padx=5)
        self.ticker_entry.insert(0, "AAPL")

        # Auswahl für den Zeitraum mit ttk.Combobox
        period_frame = ttk.Frame(self)
        period_frame.pack(pady=5)
        ttk.Label(period_frame, text="Zeitraum:").pack(side="left", padx=5)
        self.period_var = tk.StringVar()
        self.period_combo = ttk.Combobox(period_frame, textvariable=self.period_var, width=8,
                                         values=["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"])
        self.period_combo.set("1mo")
        self.period_combo.pack(side="left", padx=5)

        # Button zum Abrufen der Daten
        btn_fetch = ttk.Button(self, text="Daten abrufen", command=self.fetch_data)
        btn_fetch.pack(pady=15)

        # Label zur Anzeige des Preises
        self.price_label = ttk.Label(self, text="")
        self.price_label.pack(pady=5)

        # Frame für Diagramm
        self.chart_frame = ttk.Frame(self)
        self.chart_frame.pack(fill="both", expand=True, pady=(10,20))

    def fetch_data(self):
        ticker_symbol = self.ticker_entry.get().strip().upper()
        period = self.period_var.get()

        if not ticker_symbol:
            messagebox.showerror("Fehler", "Bitte geben Sie ein Ticker-Symbol ein.")
            return

        try:
            stock = yf.Ticker(ticker_symbol)
            data = stock.history(period=period)
            if data.empty:
                messagebox.showinfo("Info", "Keine Daten gefunden. Überprüfen Sie das Ticker-Symbol oder den Zeitraum.")
                return

            current_price = data['Close'].iloc[-1]
            self.price_label.config(text=f"Aktueller Kurs von {ticker_symbol}: {current_price:.2f} USD")
            self.plot_chart(data, ticker_symbol, period)

        except Exception as e:
            messagebox.showerror("Fehler", f"Es trat ein Fehler auf:\n{e}")

    def plot_chart(self, data, ticker_symbol, period):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        fig, ax = plt.subplots(figsize=(6,4), dpi=100)
        ax.plot(data.index, data['Close'], label="Schlusskurs", color=ACCENT_COLOR)
        ax.set_title(f"{ticker_symbol} – Schlusskursverlauf ({period})", color=FG_COLOR)
        ax.set_xlabel("Datum", color=FG_COLOR)
        ax.set_ylabel("Preis (USD)", color=FG_COLOR)
        ax.tick_params(colors=FG_COLOR)
        ax.legend(facecolor=BG_COLOR, edgecolor=FG_COLOR, labelcolor=FG_COLOR)

        # Dunkles Diagramm
        fig.patch.set_facecolor(BG_COLOR)
        ax.set_facecolor(BG_COLOR)

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


class PortfolioPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        lbl_title = ttk.Label(self, text="Ihr Portfolio", style="Header.TLabel")
        lbl_title.pack(pady=(20,10))

        form_frame = ttk.Frame(self)
        form_frame.pack(pady=5)
        ttk.Label(form_frame, text="Ticker hinzufügen:").pack(side="left", padx=5)
        self.new_ticker_entry = ttk.Entry(form_frame, width=10)
        self.new_ticker_entry.pack(side="left", padx=5)
        btn_add = ttk.Button(form_frame, text="Hinzufügen", command=self.add_ticker)
        btn_add.pack(side="left", padx=5)

        self.portfolio_list_frame = ttk.Frame(self)
        self.portfolio_list_frame.pack(pady=15, fill="both", expand=True)

        self.update_portfolio_list()

    def add_ticker(self):
        new_ticker = self.new_ticker_entry.get().strip().upper()
        if not new_ticker:
            messagebox.showerror("Fehler", "Bitte geben Sie ein Ticker-Symbol ein.")
            return
        if new_ticker in self.controller.portfolio:
            messagebox.showinfo("Info", f"{new_ticker} ist bereits in Ihrem Portfolio vorhanden.")
        else:
            self.controller.portfolio.append(new_ticker)
            messagebox.showinfo("Erfolg", f"{new_ticker} wurde hinzugefügt!")
            self.new_ticker_entry.delete(0, tk.END)
            self.update_portfolio_list()

    def update_portfolio_list(self):
        for widget in self.portfolio_list_frame.winfo_children():
            widget.destroy()

        if not self.controller.portfolio:
            lbl_empty = ttk.Label(self.portfolio_list_frame, text="Ihr Portfolio ist leer.")
            lbl_empty.pack()
        else:
            for ticker in self.controller.portfolio:
                lbl = ttk.Label(self.portfolio_list_frame, text=ticker, font=("Helvetica", 12))
                lbl.pack(anchor="w", padx=20, pady=2)


class OtherPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        lbl_title = ttk.Label(self, text="Weitere Menüpunkte", style="Header.TLabel")
        lbl_title.pack(pady=(20,10))
        lbl_info = ttk.Label(self, text="Hier können weitere Funktionen integriert werden.")
        lbl_info.pack(pady=5)


if __name__ == "__main__":
    app = App()
    app.mainloop()
