import tkinter as tk
from tkinter import ttk
import yfinance as yf
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

class FinanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Finance Tracker")
        self.root.geometry("900x700")
        self.root.minsize(900, 700)
        self.root.configure(bg="#1E1E2F")

        # Vollbildmodus
        self.is_fullscreen = False
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<Escape>", self.exit_fullscreen)

        # Titel
        self.title_label = tk.Label(root, text="Stock Price Viewer", font=("Segoe UI", 24, "bold"),
                                    bg="#1E1E2F", fg="#FFFFFF")
        self.title_label.pack(pady=20)

        # Eingabefeld und Vorschlagsbox
        self.input_frame = tk.Frame(root, bg="#1E1E2F")
        self.input_frame.pack(pady=10)

        self.symbol_entry = tk.Entry(self.input_frame, font=("Segoe UI", 14), bg="#2A2A3D", fg="#FFFFFF",
                                     insertbackground="#FFFFFF", relief="flat", highlightthickness=1,
                                     highlightbackground="#3D8EF3", highlightcolor="#5A9FF5")
        self.symbol_entry.pack(pady=5)
        self.symbol_entry.bind("<KeyRelease>", self.update_suggestions)

        self.suggestions_frame = tk.Frame(self.input_frame, bg="#1E1E2F")
        self.suggestions_scrollbar = tk.Scrollbar(self.suggestions_frame, orient="vertical")
        self.suggestions_box = tk.Listbox(self.suggestions_frame, font=("Segoe UI", 12), bg="#2A2A3D",
                                          fg="#FFFFFF", relief="flat", yscrollcommand=self.suggestions_scrollbar.set,
                                          selectbackground="#3D8EF3", activestyle="none", bd=0)
        self.suggestions_scrollbar.config(command=self.suggestions_box.yview)
        self.suggestions_box.pack(side="left", fill="both", expand=True, padx=2, pady=2)
        self.suggestions_scrollbar.pack(side="right", fill="y")
        self.suggestions_frame.pack(pady=5, fill="x")
        self.suggestions_frame.pack_forget()

        self.suggestions_box.bind("<<ListboxSelect>>", self.select_suggestion)

        # Daten abrufen Button
        self.fetch_button = ttk.Button(root, text="Fetch Data", command=self.fetch_data)
        self.fetch_button.pack(pady=20)

        # Ergebnisbereich
        self.result_label = tk.Label(root, text="",
                                     font=("Segoe UI", 16), bg="#1E1E2F", fg="#FFFFFF", wraplength=700, justify="left")
        self.result_label.pack(pady=20)

        # Diagrammbereich
        self.figure = plt.Figure(figsize=(8, 4), dpi=100)
        self.chart = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, root)
        self.chart_visible = False

        # Daten für Unternehmen und Symbole laden
        self.company_tickers = self.load_company_tickers()

    def load_company_tickers(self):
        return {
            # Aktien
            "apple": "AAPL",
            "microsoft": "MSFT",
            "google": "GOOGL",
            "tesla": "TSLA",
            "amazon": "AMZN",
            "facebook": "META",
            "netflix": "NFLX",
            "nvidia": "NVDA",
            "saudi aramco": "2222.SR",
            "berkshire hathaway": "BRK.B",
            "meta platforms": "META",
            "johnson & johnson": "JNJ",
            "jpmorgan chase": "JPM",
            "exxonmobil": "XOM",
            "visa": "V",
            "unitedhealth": "UNH",
            "home depot": "HD",
            "pfizer": "PFE",
            "walmart": "WMT",
            "roche": "ROG.SW",
            "chevron": "CVX",
            "mastercard": "MA",
            "disney": "DIS",
            "adobe": "ADBE",
            "intel": "INTC",
            "abbvie": "ABBV",
            "eli lilly": "LLY",
            "bank of america": "BAC",
            "att": "T",
            "samsung electronics": "005930.KS",
            "coca cola": "KO",
            "cisco": "CSCO",
            "novartis": "NOVN.SW",
            "mcdonalds": "MCD",
            "pepsico": "PEP",
            "merck": "MRK",
            "nike": "NKE",
            "ibm": "IBM",
            "oracle": "ORCL",
            "starbucks": "SBUX",
            "general electric": "GE",
            "citigroup": "C",
            "boeing": "BA",
            "lockheed martin": "LMT",
            "wells fargo": "WFC",
            "t-mobile us": "TMUS",
            "caterpillar": "CAT",
            "walgreens boots alliance": "WBA",
            "salesforce": "CRM",

            # ETFs
            "s&p 500": "SPY",
            "nasdaq 100": "QQQ",
            "msci world": "URTH",
            "emerging markets": "VWO",
            "dow jones": "DIA",
            "vanguard total stock market": "VTI",
            "vanguard growth": "VUG",
            "invesco qqq": "QQQ",
            "vanguard s&p 500": "VOO",
            "ishares msci emerging markets": "EEM",
            "vanguard ftse all-world": "VEU",
            "spdr gold": "GLD",
            "ishares russell 2000": "IWM",
            "schwab u.s. dividend equity": "SCHD",
            "vanguard dividend appreciation": "VIG",
            "ishares msci acwi ex-us": "ACWX",
            "ishares msci world": "URTH",
            "invesco emerging markets sovereign debt": "PCY",
            "vanek vectors gold miners": "GDX",
            "ishares u.s. real estate": "IYR",
            "vanguard reit": "VNQ",
            "ishares u.s. healthcare providers": "IHF",
            "ishares global clean energy": "ICLN",
            "spdr s&p dividend": "SDY",
            "ishares msci all country world index": "ACWI",
            "direxion daily financial bull 3x": "FAS",
            "ishares iboxx $ investment grade corporate bond": "LQD",
            "vanguard short-term bond": "BSV",
            "spdr bloomberg barclays high yield bond": "JNK",
            "invesco preferred": "PGX",
            "global x robotics & ai": "BOTZ",
            "ishares global infrastructure": "IGF",
            "vanguard consumer discretionary": "VCR",
            "ishares u.s. technology": "IYW",
            "ishares biotechnology": "IBB",
            "spdr s&p 500 growth": "SPYG",
            "ishares core msci eafe": "IEFA",
            "ishares msci emerging markets asia": "EEMA",
            "vanguard total international stock": "VXUS",
            "schwab u.s. large-cap": "SCHX",
            "invesco s&p 500 low volatility": "SPLV",
            "first trust nasdaq-100 equal weighted index": "QQEW",
            "ishares msci usa minimum volatility": "USMV",
            "ishares russell 1000 growth": "IWF",
            "ishares russell 1000 value": "IWD",
            "spdr s&p 500 value": "SPYV",
            "global x msci china financials": "CHIX",
            "vanguard health care": "VHT",
            "ishares edge msci min vol usa": "USMV",
            "schwab u.s. reit": "SCHH",
            "invesco s&p 500 equal weight": "RSP",
            "ishares iboxx $ high yield corporate bond": "HYG",
            "direxion daily technology bull 3x": "TECL",
            "vaneck vectors semiconductor": "SMH",

        }

    def fetch_data(self):
        company_name = self.symbol_entry.get().strip().lower()
        if not company_name:
            self.result_label.config(text="Please enter a valid company name or symbol.")
            return

        symbol = self.company_tickers.get(company_name, company_name)

        try:
            stock = yf.Ticker(symbol)
            hist_data = stock.history(period="1mo")

            if hist_data.empty:
                self.result_label.config(text=f"No data found for {symbol.upper()}.")
                return

            # Preis anzeigen
            price = hist_data['Close'].iloc[-1]
            self.result_label.config(text=f"Current price of {symbol.upper()}: {price:.2f} USD")

            # Diagramm anzeigen und aktualisieren
            self.chart.clear()
            self.chart.plot(hist_data.index, hist_data['Close'], label="Close Price", color="#3D8EF3")
            self.chart.set_title(f"Price Trend for {symbol.upper()}", fontsize=14)
            self.chart.set_xlabel("Date", fontsize=12)
            self.chart.set_ylabel("Price (USD)", fontsize=12)
            self.chart.legend()

            if not self.chart_visible:
                self.canvas.get_tk_widget().pack(pady=20)
                self.chart_visible = True

            self.canvas.draw()

        except Exception as e:
            self.result_label.config(text="Error fetching data. Please try again later.")
            print(f"Error: {e}")

    def update_suggestions(self, event=None):
        search_term = self.symbol_entry.get().strip().lower()
        self.suggestions_box.delete(0, tk.END)

        if search_term:
            matches = [(name, ticker) for name, ticker in self.company_tickers.items() if search_term in name]

            if matches:
                self.suggestions_frame.pack(pady=5, fill="x")
                self.suggestions_box.config(height=min(len(matches), 5))
                for name, ticker in matches:
                    self.suggestions_box.insert(tk.END, f"{name} ({ticker})")
            else:
                self.suggestions_frame.pack_forget()
        else:
            self.suggestions_frame.pack_forget()

    def select_suggestion(self, event=None):
        selected = self.suggestions_box.get(self.suggestions_box.curselection())
        name = selected.split(" (")[0]
        self.symbol_entry.delete(0, tk.END)
        self.symbol_entry.insert(0, name)
        self.suggestions_frame.pack_forget()

    def toggle_fullscreen(self, event=None):
        self.is_fullscreen = not self.is_fullscreen
        self.root.attributes("-fullscreen", self.is_fullscreen)

    def exit_fullscreen(self, event=None):
        self.is_fullscreen = False
        self.root.attributes("-fullscreen", False)

if __name__ == "__main__":
    root = tk.Tk()
    app = FinanceApp(root)
    root.mainloop()
