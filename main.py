from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import yfinance as yf


def fetch_stock_history(ticker: str, quantity: int, period: str) -> pd.DataFrame:
    """
    Holt den historischen Aktienkurs eines Tickers mit yfinance und berechnet den
    Gesamtwert (TotalValue). Schlägt der Abruf fehl oder sind keine Daten vorhanden,
    wird eine ValueError geworfen.
    """
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)

    # Zeitzone entfernen, damit Pandas nicht meckert (tz-naive vs. tz-aware).
    history.index = history.index.tz_localize(None)

    if history.empty:
        raise ValueError(f"Keine Daten für {ticker} verfügbar (Zeitraum: {period}).")

    # In DataFrame konvertieren und Spalten hinzufügen
    history = history.reset_index()
    history["Ticker"] = ticker
    # TotalValue hier ist "Close * quantity" - rein zeitabhängig
    history["TotalValue"] = history["Close"] * quantity
    return history


class App(tb.Window):
    """
    Hauptanwendung als ttkbootstrap-Fenster.
    """

    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Aktien & ETF Portfolio")

        # Mindestgröße (nicht kleiner als 640x420):
        self.minsize(640, 420)

        # Portfolio speichert jetzt "avg_price"
        # -> z.B. {"ticker": "AAPL", "quantity": 10, "avg_price": 150.0}
        self.portfolio_data = []

        # Hauptlayout: links Sidebar, rechts Container
        self.grid_columnconfigure(0, weight=0)  # Sidebar fix
        self.grid_columnconfigure(1, weight=1)  # Hauptinhalt
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_frames()

        # Beim Schließen: Threads sauber stoppen
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Starte mit dem Dashboard
        self.show_frame("DashboardPage")

    def create_sidebar(self):
        self.sidebar = tb.Frame(self, bootstyle="secondary")
        self.sidebar.grid(row=0, column=0, sticky="ns")

        btn_dashboard = tb.Button(
            self.sidebar,
            text="Dashboard",
            command=lambda: self.show_frame("DashboardPage"),
            bootstyle="outline-primary"
        )
        btn_dashboard.pack(pady=(20, 10), padx=10, fill="x")

        btn_market = tb.Button(
            self.sidebar,
            text="Markt",
            command=lambda: self.show_frame("MarketPage"),
            bootstyle="outline-primary"
        )
        btn_market.pack(pady=10, padx=10, fill="x")

        btn_portfolio = tb.Button(
            self.sidebar,
            text="Portfolio",
            command=lambda: self.show_frame("PortfolioPage"),
            bootstyle="outline-primary"
        )
        btn_portfolio.pack(pady=10, padx=10, fill="x")

    def create_frames(self):
        """
        Erstellt und verwaltet die Seiten (Frames) im Container.
        """
        self.container = tb.Frame(self)
        self.container.grid(row=0, column=1, sticky="nsew")

        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)

        self.frames = {}
        for F in (DashboardPage, MarketPage, PortfolioPage):
            frame = F(parent=self.container, app=self)
            page_name = F.__name__
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def show_frame(self, page_name: str):
        frame = self.frames[page_name]
        frame.tkraise()

    def on_close(self):
        """
        Beendet alle laufenden Threads und schließt die Anwendung.
        """
        for frame in self.frames.values():
            if hasattr(frame, "stop_threads"):
                frame.stop_threads()
        self.destroy()


class DashboardPage(tb.Frame):
    """
    Dashboard, in dem jetzt der Zeitraum ausgewählt werden kann
    und zusätzlich die Rendite seit Kauf angezeigt wird.
    """

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        # Executor für asynchrone Datenabfragen
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        # Titel
        title = tb.Label(self, text="Dashboard", font=("Helvetica", 24, "bold"))
        title.pack(pady=10)

        # *** NEU: Zeitraum-Auswahl + Aktualisieren-Button ***
        period_container = tb.Frame(self)
        period_container.pack(pady=5, anchor="center")

        tb.Label(period_container, text="Zeitraum:", font=("Helvetica", 12)).pack(side="left", padx=5)

        self.period_var = tb.StringVar(value="1mo")
        self.period_combo = tb.Combobox(
            period_container,
            textvariable=self.period_var,
            values=["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"],
            width=8
        )
        self.period_combo.pack(side="left", padx=5)

        btn_refresh = tb.Button(
            period_container, text="Aktualisieren", command=self.update_dashboard, bootstyle="primary"
        )
        btn_refresh.pack(side="left", padx=5)

        # Container für Diagramme
        self.grid_container = tb.Frame(self)
        self.grid_container.pack(fill="both", expand=True)

        self.grid_container.columnconfigure(0, weight=1)
        self.grid_container.columnconfigure(1, weight=1)
        self.grid_container.rowconfigure(0, weight=1)
        self.grid_container.rowconfigure(1, weight=1)

        # Initiales Laden
        self.update_dashboard()

    def update_dashboard(self):
        """
        Startet den asynchronen Datenabruf im gewählten Zeitraum.
        """
        for widget in self.grid_container.winfo_children():
            widget.destroy()

        if not self.app.portfolio_data:
            empty_label = tb.Label(
                self.grid_container,
                text="Ihr Portfolio ist leer. Bitte fügen Sie Einträge hinzu.",
                font=("Helvetica", 14)
            )
            empty_label.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")
        else:
            # Async-Aufruf
            self.future = self.executor.submit(self.load_and_display_data)

    def load_and_display_data(self):
        """
        Lädt die Daten (pro Ticker) für den gewählten Zeitraum
        und zeigt die Diagramme an.
        """
        try:
            data = self.get_portfolio_data()
            # Nach dem Laden in den Haupt-Thread zurückkehren:
            self.after(0, lambda: self.display_charts(data))
        except Exception as e:
            self.after(0, lambda: self.show_error(e))

    def display_charts(self, data: pd.DataFrame):
        """
        Zeigt das Kreisdiagramm, Kennzahlen und Liniendiagramm an.
        Zusätzlich berechnen wir jetzt die Gesamtrendite „seit Kauf“.
        """
        bg_color = self.app.cget("background")

        # Oben links: Kreisdiagramm
        pie_frame = tb.Frame(self.grid_container)
        pie_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        pie_frame.columnconfigure(0, weight=1)
        pie_frame.rowconfigure(0, weight=1)

        # composition = Summe der "TotalValue" (=> 'Close' * 'quantity') pro Ticker
        composition = data.groupby("Ticker")["TotalValue"].last()
        # (last() => aktueller Wert am Ende des Zeitraums)

        fig_pie = Figure(facecolor=bg_color)
        ax_pie = fig_pie.add_subplot(111)
        ax_pie.pie(composition, labels=composition.index, autopct="%1.1f%%",
                   textprops={"color": "white"})
        ax_pie.set_title("Portfolio-Zusammensetzung", color="white")
        fig_pie.tight_layout()

        canvas_pie = FigureCanvasTkAgg(fig_pie, master=pie_frame)
        canvas_pie.draw()
        canvas_pie.get_tk_widget().pack(fill="both", expand=True)

        # Oben rechts: Kennzahlen
        info_frame = tb.Frame(self.grid_container)
        info_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        info_frame.columnconfigure(0, weight=1)

        # total_values: Summe des Portfolios pro Tag (alle Ticker)
        total_values = data.groupby("Date")["TotalValue"].sum().sort_index()

        # Tagesveränderung (letzter Tag - vorletzter Tag)
        if len(total_values) >= 2:
            daily_change = total_values.iloc[-1] - total_values.iloc[-2]
            daily_percent = 0
            if total_values.iloc[-2] != 0:
                daily_percent = (daily_change / total_values.iloc[-2]) * 100
        else:
            daily_change = 0
            daily_percent = 0

        # Aktueller Wert im Chart (d.h. an letztem Datum des gewählten Zeitraums)
        if not total_values.empty:
            current_total = total_values.iloc[-1]
        else:
            current_total = 0

        # Performance (Zeitraum): vom ersten Tag im Datensatz bis zum letzten
        if len(total_values) >= 2:
            initial_value = total_values.iloc[0]
            if initial_value != 0:
                period_return = ((current_total - initial_value) / initial_value) * 100
            else:
                period_return = 0
        else:
            period_return = 0

        # Top-/Flop-Performer (auf Basis der Zeitreihe)
        # Wir vergleichen den Wert am ersten Tag vs. letzten Tag pro Ticker
        perf_dict = {}
        for ticker, group in data.groupby("Ticker"):
            group_sorted = group.sort_values("Date")
            start_val = group_sorted["TotalValue"].iloc[0]
            end_val = group_sorted["TotalValue"].iloc[-1]
            if start_val != 0:
                pct = ((end_val - start_val) / start_val) * 100
            else:
                pct = 0
            perf_dict[ticker] = pct

        if perf_dict:
            top_ticker = max(perf_dict, key=perf_dict.get)
            top_pct = perf_dict[top_ticker]
            flop_ticker = min(perf_dict, key=perf_dict.get)
            flop_pct = perf_dict[flop_ticker]
        else:
            top_ticker, flop_ticker, top_pct, flop_pct = "n/a", "n/a", 0, 0

        # --- NEU: Berechnung der Rendite seit Kauf ---
        # Portfolio-Kaufwert = Summe aus (quantity * avg_price)
        portfolio_cost = 0
        for item in self.app.portfolio_data:
            portfolio_cost += item["quantity"] * item["avg_price"]

        # Aktueller Portfoliowert (aus composition oder total_values am letzten Tag)
        # Wir nehmen composition.sum(), da composition = "Letzter Wert pro Ticker"
        portfolio_value = composition.sum() if not composition.empty else 0

        # Rendite seit Kauf
        if portfolio_cost > 0:
            total_return_since_purchase = ((portfolio_value - portfolio_cost) / portfolio_cost) * 100
        else:
            total_return_since_purchase = 0

        # Anzeige der Kennzahlen (Labels)
        lbl_daily_abs = tb.Label(
            info_frame,
            text=f"Tagesveränderung: {daily_change:,.2f} USD",
            font=("Helvetica", 14, "bold"),
            foreground="green" if daily_change >= 0 else "red"
        )
        lbl_daily_abs.grid(row=0, column=0, pady=(10, 5), sticky="ew")

        lbl_daily_pct = tb.Label(
            info_frame,
            text=f"Prozentuale Veränderung: {daily_percent:.2f}%",
            font=("Helvetica", 13),
            foreground="white"
        )
        lbl_daily_pct.grid(row=1, column=0, pady=5, sticky="ew")

        lbl_total = tb.Label(
            info_frame,
            text=f"Aktueller Wert: {current_total:,.2f} USD",
            font=("Helvetica", 14, "bold"),
            foreground="white"
        )
        lbl_total.grid(row=2, column=0, pady=5, sticky="ew")

        # Zeitraum-Performance:
        lbl_period_return = tb.Label(
            info_frame,
            text=f"Performance (Zeitraum): {period_return:.2f}%",
            font=("Helvetica", 13),
            foreground="white"
        )
        lbl_period_return.grid(row=3, column=0, pady=5, sticky="ew")

        # Gesamtrendite seit Kauf
        lbl_since_purchase = tb.Label(
            info_frame,
            text=f"Gesamtrendite (seit Kauf): {total_return_since_purchase:.2f}%",
            font=("Helvetica", 13),
            foreground="white"
        )
        lbl_since_purchase.grid(row=4, column=0, pady=5, sticky="ew")

        lbl_top = tb.Label(
            info_frame,
            text=f"Top Performer: {top_ticker} ({top_pct:.2f}%)",
            font=("Helvetica", 13),
            foreground="white"
        )
        lbl_top.grid(row=5, column=0, pady=5, sticky="ew")

        lbl_flop = tb.Label(
            info_frame,
            text=f"Flop Performer: {flop_ticker} ({flop_pct:.2f}%)",
            font=("Helvetica", 13),
            foreground="white"
        )
        lbl_flop.grid(row=6, column=0, pady=(5, 10), sticky="ew")

        # Unten: Liniendiagramm (gesamter Portfoliowert im Zeitverlauf)
        line_frame = tb.Frame(self.grid_container)
        line_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        line_frame.columnconfigure(0, weight=1)
        line_frame.rowconfigure(0, weight=1)

        fig_line = Figure(facecolor=bg_color)
        ax_line = fig_line.add_subplot(111)
        ax_line.plot(
            total_values.index, total_values.values,
            label="Portfolio", color="#4a90e2"
        )
        ax_line.set_title("Portfolio-Veränderungen", color="white")
        ax_line.set_xlabel("Datum", color="white")
        ax_line.set_ylabel("Wert (USD)", color="white")
        ax_line.tick_params(colors="white")
        ax_line.legend(facecolor=bg_color, labelcolor="white")
        fig_line.tight_layout()

        canvas_line = FigureCanvasTkAgg(fig_line, master=line_frame)
        canvas_line.draw()
        canvas_line.get_tk_widget().pack(fill="both", expand=True)

    def show_error(self, error: Exception):
        error_label = tb.Label(
            self.grid_container,
            text=f"Fehler beim Laden der Daten: {error}",
            font=("Helvetica", 14),
            foreground="red"
        )
        error_label.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")

    def get_portfolio_data(self) -> pd.DataFrame:
        """
        Holt die Daten für alle Ticker im Portfolio für den gewählten Zeitraum.
        """
        data_frames = []
        period = self.period_var.get()  # Zeitraum aus Combobox
        for item in self.app.portfolio_data:
            ticker = item["ticker"]
            quantity = item["quantity"]
            df = fetch_stock_history(ticker, quantity, period)
            data_frames.append(df)
        return pd.concat(data_frames, ignore_index=True)

    def stop_threads(self):
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False)


class MarketPage(tb.Frame):
    """
    Seite zum Abrufen und Anzeigen von Marktdaten für ein Ticker-Symbol.
    """

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        title = tb.Label(self, text="Aktueller Markt", font=("Helvetica", 24, "bold"))
        title.pack(pady=20)

        input_container = tb.Frame(self)
        input_container.pack(pady=10, anchor="center")

        # Ticker-Eingabe
        ticker_frame = tb.Frame(input_container)
        ticker_frame.pack(pady=5, anchor="center")
        ticker_label = tb.Label(ticker_frame, text="Ticker-Symbol:")
        ticker_label.pack(side="left", padx=5)
        self.ticker_entry = tb.Entry(ticker_frame, width=15)
        self.ticker_entry.pack(side="left", padx=5)
        self.ticker_entry.insert(0, "AAPL")

        # Zeitraum
        period_frame = tb.Frame(input_container)
        period_frame.pack(pady=5, anchor="center")
        period_label = tb.Label(period_frame, text="Zeitraum:")
        period_label.pack(side="left", padx=5)
        self.period_var = tb.StringVar(value="1mo")
        self.period_combo = tb.Combobox(
            period_frame,
            textvariable=self.period_var,
            width=12,
            values=["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"]
        )
        self.period_combo.pack(side="left", padx=5)

        btn_fetch = tb.Button(
            input_container, text="Daten abrufen",
            command=self.fetch_data, bootstyle="primary"
        )
        btn_fetch.pack(pady=10, anchor="center")

        self.price_label = tb.Label(self, text="")
        self.price_label.pack(pady=5, anchor="center")

        self.chart_frame = tb.Frame(self)
        self.chart_frame.pack(fill="both", expand=True, pady=10)

    def fetch_data(self):
        ticker_symbol = self.ticker_entry.get().strip().upper()
        period = self.period_var.get()
        if not ticker_symbol:
            return

        self.future = self.executor.submit(self.fetch_market_data, ticker_symbol, period)

    def fetch_market_data(self, ticker_symbol: str, period: str):
        try:
            stock = yf.Ticker(ticker_symbol)
            data = stock.history(period=period)
            data.index = data.index.tz_localize(None)

            if data.empty:
                self.after(0, lambda: self.price_label.config(
                    text=f"Keine Daten für {ticker_symbol} im Zeitraum {period}."))
                return

            current_price = data["Close"].iloc[-1]
            self.after(0, lambda: self.price_label.config(
                text=f"Aktueller Kurs von {ticker_symbol}: {current_price:.2f} USD"))

            self.after(0, lambda: self.plot_chart(data, ticker_symbol, period))

        except Exception as e:
            self.after(0, lambda: self.price_label.config(
                text=f"Fehler beim Abrufen von Daten zu {ticker_symbol}: {e}"))

    def plot_chart(self, data: pd.DataFrame, ticker_symbol: str, period: str):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        fig = Figure()
        ax = fig.add_subplot(111)
        ax.plot(data.index, data["Close"], label="Schlusskurs", color="#4a90e2")
        ax.set_title(f"{ticker_symbol} – Schlusskursverlauf ({period})", color="white")
        ax.set_xlabel("Datum", color="white")
        ax.set_ylabel("Preis (USD)", color="white")
        ax.tick_params(colors="white")
        ax.legend(facecolor=self.app.cget("background"), labelcolor="white")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def stop_threads(self):
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False)


class PortfolioPage(tb.Frame):
    """
    Seite zum Hinzufügen und Anzeigen von Portfolio-Einträgen.
    Dabei wird auch der durchschnittliche Kaufpreis berücksichtigt.
    """

    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        title = tb.Label(self, text="Ihr Portfolio", font=("Helvetica", 24, "bold"))
        title.pack(pady=20)

        input_container = tb.Frame(self)
        input_container.pack(pady=10, anchor="center")

        form_frame = tb.Frame(input_container)
        form_frame.grid(row=0, column=0, pady=5)

        # Ticker
        label_ticker = tb.Label(form_frame, text="Ticker:")
        label_ticker.grid(row=0, column=0, padx=5)
        self.ticker_entry = tb.Entry(form_frame, width=10)
        self.ticker_entry.grid(row=0, column=1, padx=5)

        # Anzahl
        label_quantity = tb.Label(form_frame, text="Anzahl:")
        label_quantity.grid(row=0, column=2, padx=5)
        self.quantity_entry = tb.Entry(form_frame, width=5)
        self.quantity_entry.grid(row=0, column=3, padx=5)

        # Kaufpreis
        label_price = tb.Label(form_frame, text="Kaufpreis:")
        label_price.grid(row=0, column=4, padx=5)
        self.price_entry = tb.Entry(form_frame, width=7)
        self.price_entry.grid(row=0, column=5, padx=5)

        # Hinzufügen-Button
        btn_add = tb.Button(
            input_container, text="Hinzufügen",
            command=self.add_ticker, bootstyle="primary"
        )
        btn_add.grid(row=1, column=0, pady=5)

        # Portfolio-Anzeige
        self.portfolio_frame = tb.Frame(self)
        self.portfolio_frame.pack(pady=10, fill="both", expand=True)

        self.update_portfolio()

    def add_ticker(self):
        """
        Fügt einen Ticker mit Menge und Kaufpreis hinzu.
        Bei mehrfachem Kauf desselben Tickers wird der Durchschnittspreis neu berechnet.
        """
        new_ticker = self.ticker_entry.get().strip().upper()
        qty_str = self.quantity_entry.get().strip()
        price_str = self.price_entry.get().strip()

        if new_ticker and qty_str.isdigit() and self.is_float(price_str):
            new_qty = int(qty_str)
            new_price = float(price_str)

            # Prüfen, ob der Ticker bereits existiert
            existing = next((item for item in self.app.portfolio_data if item["ticker"] == new_ticker), None)
            if existing is None:
                # Neuer Eintrag
                self.app.portfolio_data.append({
                    "ticker": new_ticker,
                    "quantity": new_qty,
                    "avg_price": new_price
                })
            else:
                # Ticker schon vorhanden: Menge addieren, avg_price neu berechnen
                old_qty = existing["quantity"]
                old_price = existing["avg_price"]

                total_cost_old = old_qty * old_price
                total_cost_new = new_qty * new_price
                total_qty = old_qty + new_qty

                new_avg_price = (total_cost_old + total_cost_new) / total_qty

                existing["quantity"] = total_qty
                existing["avg_price"] = new_avg_price

            # Portfolio-Liste und Dashboard aktualisieren
            self.update_portfolio()
            self.app.frames["DashboardPage"].update_dashboard()

        # Eingabefelder leeren
        self.ticker_entry.delete(0, "end")
        self.quantity_entry.delete(0, "end")
        self.price_entry.delete(0, "end")

    def is_float(self, value: str) -> bool:
        try:
            float(value)
            return True
        except ValueError:
            return False

    def update_portfolio(self):
        # Alte Einträge entfernen
        for widget in self.portfolio_frame.winfo_children():
            widget.destroy()

        if not self.app.portfolio_data:
            lbl = tb.Label(
                self.portfolio_frame,
                text="Ihr Portfolio ist leer.",
                anchor="center"
            )
            lbl.pack(padx=10, pady=10, fill="x")
        else:
            # Für jeden Ticker eine Info-Zeile
            for idx, item in enumerate(self.app.portfolio_data):
                ticker_card = tb.Frame(self.portfolio_frame, bootstyle="info", padding=10)
                ticker_card.pack(padx=10, pady=5, fill="x")

                info_str = (
                    f"{item['ticker']} – "
                    f"{item['quantity']} Stück – "
                    f"Durchschn. Kaufpreis: {item['avg_price']:.2f} USD"
                )

                lbl = tb.Label(
                    ticker_card,
                    text=info_str,
                    font=("Helvetica", 14, "bold"),
                    anchor="w"
                )
                lbl.pack(side="left")

    def stop_threads(self):
        pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
