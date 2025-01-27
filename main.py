import logging
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import yfinance as yf

from database import Database

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


def fetch_stock_history(ticker: str, quantity: int, period: str) -> pd.DataFrame:
    stock = yf.Ticker(ticker)
    history = stock.history(period=period)

    if history.empty:
        logger.warning(f"Keine Daten von yfinance für {ticker} (Zeitraum={period}).")
        return pd.DataFrame()

    if isinstance(history.index, pd.DatetimeIndex):
        try:
            history.index = history.index.tz_localize(None)
        except TypeError:
            pass

    history = history.reset_index()
    history["Ticker"] = ticker
    history["TotalValue"] = history["Close"] * quantity
    return history


def get_theme_colors(theme_name: str):
    if theme_name == "superhero":
        return ("#2b2b2b", "white")
    else:
        return ("white", "black")


class App(tb.Window):
    def __init__(self):
        super().__init__(themename="superhero")
        self.title("Aktien & ETF Portfolio - Modern UI")
        self.geometry("900x600")

        self.db = Database(db_path="portfolio.db")
        self.portfolio_data = []
        self.reload_portfolio_data()

        self.create_appbar()

        self.notebook = tb.Notebook(self, bootstyle="secondary")
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.frames = {}
        pages = [
            (DashboardPage, "Dashboard"),
            (MarketPage, "Markt"),
            (PortfolioPage, "Portfolio")
        ]
        for page_class, tab_name in pages:
            frame = page_class(self.notebook, app=self)
            self.frames[page_class.__name__] = frame
            self.notebook.add(frame, text=tab_name)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_appbar(self):
        appbar = tb.Frame(self, padding=10)
        appbar.pack(side="top", fill="x")

        lbl_title = tb.Label(
            appbar,
            text="Aktien & ETF Portfolio",
            font=("Helvetica", 24, "bold")
        )
        lbl_title.pack(side="left", padx=(10, 20))

        btn_theme = tb.Button(
            appbar,
            text="Theme wechseln",
            command=self.toggle_theme,
            bootstyle="info"
        )
        btn_theme.pack(side="right", padx=10)

    def toggle_theme(self):
        current_theme = self.style.theme.name
        if current_theme == "superhero":
            self.style.theme_use("flatly")
        else:
            self.style.theme_use("superhero")

        for frame in self.frames.values():
            if hasattr(frame, "on_theme_change"):
                frame.on_theme_change()

    def reload_portfolio_data(self):
        try:
            self.portfolio_data = self.db.load_portfolio()
        except Exception as e:
            logger.error(f"Fehler beim Laden des Portfolios: {e}")
            messagebox.showerror("DB-Fehler", f"Fehler beim Laden des Portfolios:\n{e}")

    def on_close(self):
        for frame in self.frames.values():
            if hasattr(frame, "stop_threads"):
                frame.stop_threads()
        self.destroy()


class DashboardPage(tb.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        lbl_title = tb.Label(self, text="Dashboard", font=("Helvetica", 22, "bold"))
        lbl_title.pack(pady=(10, 5))

        period_container = tb.Frame(self)
        period_container.pack(pady=5)

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
            period_container,
            text="Aktualisieren",
            command=self.update_dashboard,
            bootstyle="primary"
        )
        btn_refresh.pack(side="left", padx=5)

        self.grid_container = tb.Frame(self)
        self.grid_container.pack(fill="both", expand=True, padx=10, pady=10)

        self.grid_container.columnconfigure(0, weight=1)
        self.grid_container.columnconfigure(1, weight=1)
        self.grid_container.rowconfigure(0, weight=1)
        self.grid_container.rowconfigure(1, weight=1)

        self.update_dashboard()

    def on_theme_change(self):
        self.update_dashboard()

    def update_dashboard(self):
        for widget in self.grid_container.winfo_children():
            widget.destroy()

        if not self.app.portfolio_data:
            lbl_empty = tb.Label(
                self.grid_container,
                text="Ihr Portfolio ist leer. Bitte fügen Sie Einträge hinzu.",
                font=("Helvetica", 14)
            )
            lbl_empty.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")
        else:
            self.future = self.executor.submit(self.load_and_display_data)

    def load_and_display_data(self):
        try:
            data = self.get_portfolio_data()
            self.after(0, lambda: self.display_charts(data))
        except Exception as e:
            logger.error(f"Fehler im Dashboard: {e}")
            self.after(0, lambda: self.show_error(e))

    def display_charts(self, data: pd.DataFrame):
        theme_name = self.style.theme.name
        bg_color, text_color = get_theme_colors(theme_name)

        if data.empty:
            lbl_empty = tb.Label(
                self.grid_container,
                text="Keine Kursdaten verfügbar für Ihre Ticker.",
                font=("Helvetica", 14),
                foreground="yellow"
            )
            lbl_empty.grid(row=0, column=0, columnspan=2, pady=20, sticky="nsew")
            return

        pie_frame = tb.Frame(self.grid_container)
        pie_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        pie_frame.columnconfigure(0, weight=1)
        pie_frame.rowconfigure(0, weight=1)

        composition = data.groupby("Ticker")["TotalValue"].last()
        from matplotlib.figure import Figure
        fig_pie = Figure(facecolor=bg_color)
        ax_pie = fig_pie.add_subplot(111)
        ax_pie.set_facecolor(bg_color)
        wedges, texts, autotexts = ax_pie.pie(
            composition, labels=composition.index, autopct="%1.1f%%",
            textprops={"color": text_color}
        )
        ax_pie.set_title("Portfolio-Zusammensetzung", color=text_color)
        fig_pie.tight_layout()

        canvas_pie = FigureCanvasTkAgg(fig_pie, master=pie_frame)
        canvas_pie.draw()
        canvas_pie.get_tk_widget().pack(fill="both", expand=True)

        info_frame = tb.Frame(self.grid_container)
        info_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        info_frame.columnconfigure(0, weight=1)

        total_values = data.groupby("Date")["TotalValue"].sum().sort_index()

        daily_change, daily_percent = 0, 0
        if len(total_values) >= 2:
            daily_change = total_values.iloc[-1] - total_values.iloc[-2]
            if total_values.iloc[-2] != 0:
                daily_percent = (daily_change / total_values.iloc[-2]) * 100

        current_total = total_values.iloc[-1] if not total_values.empty else 0

        period_return = 0
        if len(total_values) >= 2:
            initial_value = total_values.iloc[0]
            if initial_value != 0:
                period_return = ((current_total - initial_value) / initial_value) * 100

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
            top_ticker, top_pct, flop_ticker, flop_pct = "n/a", 0, "n/a", 0

        portfolio_cost = sum(i["quantity"] * i["avg_price"] for i in self.app.portfolio_data)
        portfolio_value = composition.sum() if not composition.empty else 0
        if portfolio_cost > 0:
            total_return_since_purchase = ((portfolio_value - portfolio_cost) / portfolio_cost) * 100
        else:
            total_return_since_purchase = 0

        fg_change = "green" if daily_change >= 0 else "red"

        lbl_daily_abs = tb.Label(
            info_frame,
            text=f"Tagesveränderung: {daily_change:,.2f} USD",
            font=("Helvetica", 14, "bold"),
            foreground=fg_change
        )
        lbl_daily_abs.grid(row=0, column=0, pady=(10, 5), sticky="ew")

        lbl_daily_pct = tb.Label(
            info_frame,
            text=f"Prozentuale Veränderung: {daily_percent:.2f}%",
            font=("Helvetica", 13),
            foreground=text_color
        )
        lbl_daily_pct.grid(row=1, column=0, pady=5, sticky="ew")

        lbl_total = tb.Label(
            info_frame,
            text=f"Aktueller Wert: {current_total:,.2f} USD",
            font=("Helvetica", 14, "bold"),
            foreground=text_color
        )
        lbl_total.grid(row=2, column=0, pady=5, sticky="ew")

        lbl_period_return = tb.Label(
            info_frame,
            text=f"Performance (Zeitraum): {period_return:.2f}%",
            font=("Helvetica", 13),
            foreground=text_color
        )
        lbl_period_return.grid(row=3, column=0, pady=5, sticky="ew")

        lbl_since_purchase = tb.Label(
            info_frame,
            text=f"Gesamtrendite (seit Kauf): {total_return_since_purchase:.2f}%",
            font=("Helvetica", 13),
            foreground=text_color
        )
        lbl_since_purchase.grid(row=4, column=0, pady=5, sticky="ew")

        lbl_top = tb.Label(
            info_frame,
            text=f"Top Performer: {top_ticker} ({top_pct:.2f}%)",
            font=("Helvetica", 13),
            foreground=text_color
        )
        lbl_top.grid(row=5, column=0, pady=5, sticky="ew")

        lbl_flop = tb.Label(
            info_frame,
            text=f"Flop Performer: {flop_ticker} ({flop_pct:.2f}%)",
            font=("Helvetica", 13),
            foreground=text_color
        )
        lbl_flop.grid(row=6, column=0, pady=(5, 10), sticky="ew")

        line_frame = tb.Frame(self.grid_container)
        line_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        line_frame.columnconfigure(0, weight=1)
        line_frame.rowconfigure(0, weight=1)

        fig_line = Figure(facecolor=bg_color)
        ax_line = fig_line.add_subplot(111)
        ax_line.set_facecolor(bg_color)
        ax_line.plot(total_values.index, total_values.values, label="Portfolio", color="#4a90e2")

        ax_line.set_title("Portfolio-Veränderungen", color=text_color)
        ax_line.set_xlabel("Datum", color=text_color)
        ax_line.set_ylabel("Wert (USD)", color=text_color)
        ax_line.tick_params(colors=text_color)
        ax_line.legend(facecolor=bg_color, labelcolor=text_color)
        fig_line.tight_layout()

        canvas_line = FigureCanvasTkAgg(fig_line, master=line_frame)
        canvas_line.draw()
        canvas_line.get_tk_widget().pack(fill="both", expand=True)

    def show_error(self, error: Exception):
        messagebox.showerror("Fehler im Dashboard", str(error))

    def get_portfolio_data(self) -> pd.DataFrame:
        frames = []
        period = self.period_var.get()
        for item in self.app.portfolio_data:
            ticker = item["ticker"]
            qty = item["quantity"]
            df = fetch_stock_history(ticker, qty, period)
            if not df.empty:
                frames.append(df)
            else:
                logger.warning(f"Ticker '{ticker}' liefert keine Daten -> ignoriert im Dashboard")

        if frames:
            return pd.concat(frames, ignore_index=True)
        else:
            return pd.DataFrame()

    def stop_threads(self):
        if self.future and not self.future.done():
            self.future.cancel()
        self.executor.shutdown(wait=False)


class MarketPage(tb.Frame):
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        self.executor = ThreadPoolExecutor(max_workers=1)
        self.future = None

        lbl_title = tb.Label(self, text="Marktdaten", font=("Helvetica", 22, "bold"))
        lbl_title.pack(pady=(10, 5))

        input_container = tb.Frame(self)
        input_container.pack(pady=10)

        ticker_frame = tb.Frame(input_container)
        ticker_frame.pack(pady=5)
        lbl_ticker = tb.Label(ticker_frame, text="Ticker-Symbol:")
        lbl_ticker.pack(side="left", padx=5)

        self.ticker_entry = tb.Entry(ticker_frame, width=15)
        self.ticker_entry.pack(side="left", padx=5)
        # Leer lassen

        period_frame = tb.Frame(input_container)
        period_frame.pack(pady=5)
        lbl_period = tb.Label(period_frame, text="Zeitraum:")
        lbl_period.pack(side="left", padx=5)
        self.period_var = tb.StringVar(value="1mo")
        self.period_combo = tb.Combobox(
            period_frame,
            textvariable=self.period_var,
            width=12,
            values=["1d", "5d", "1mo", "3mo", "6mo", "1y", "5y", "max"]
        )
        self.period_combo.pack(side="left", padx=5)

        btn_fetch = tb.Button(
            input_container,
            text="Daten abrufen",
            command=self.fetch_data,
            bootstyle="primary"
        )
        btn_fetch.pack(pady=10)

        self.price_label = tb.Label(self, text="", font=("Helvetica", 14))
        self.price_label.pack(pady=5)

        self.chart_frame = tb.Frame(self)
        self.chart_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def on_theme_change(self):
        pass

    def fetch_data(self):
        ticker_symbol = self.ticker_entry.get().strip().upper()
        period = self.period_var.get()
        if not ticker_symbol:
            return
        self.future = self.executor.submit(self._fetch_market_data, ticker_symbol, period)

    def _fetch_market_data(self, ticker_symbol: str, period: str):
        try:
            df = fetch_stock_history(ticker_symbol, quantity=1, period=period)
            if df.empty:
                self.after(0, lambda: self.price_label.config(
                    text=f"Keine Daten für {ticker_symbol} im Zeitraum {period}."))
                return

            current_price = df["Close"].iloc[-1]
            self.after(0, lambda: self.price_label.config(
                text=f"Aktueller Kurs von {ticker_symbol}: {current_price:.2f} USD"))

            self.after(0, lambda: self.plot_chart(df, ticker_symbol, period))
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von Daten zu {ticker_symbol}: {e}")
            self.after(0, lambda: self.price_label.config(text=f"Fehler: {e}"))

    def plot_chart(self, data: pd.DataFrame, ticker_symbol: str, period: str):
        for widget in self.chart_frame.winfo_children():
            widget.destroy()

        theme_name = self.style.theme.name
        bg_color, text_color = get_theme_colors(theme_name)

        fig = Figure(facecolor=bg_color)
        ax = fig.add_subplot(111)
        ax.set_facecolor(bg_color)
        ax.plot(data["Date"], data["Close"], label="Schlusskurs", color="#4a90e2")

        ax.set_title(f"{ticker_symbol} – Schlusskursverlauf ({period})", color=text_color)
        ax.set_xlabel("Datum", color=text_color)
        ax.set_ylabel("Preis (USD)", color=text_color)
        ax.tick_params(colors=text_color)
        ax.legend(facecolor=bg_color, labelcolor=text_color)
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
    Das Layout hier wurde angepasst, damit die Anzeige 'zentral unten unter der Eingabe' liegt.
    """
    def __init__(self, parent, app: App):
        super().__init__(parent)
        self.app = app

        # Wir legen ein Haupt-Grid an, in dem die Eingaben oben, die Portfolioanzeige unten ist
        self.columnconfigure(0, weight=1)
        # Eingabe-Container in Zeile 0, Portfolio-Anzeige in Zeile 1

        lbl_title = tb.Label(self, text="Portfolio-Verwaltung", font=("Helvetica", 22, "bold"))
        lbl_title.grid(row=0, column=0, pady=(10, 5))

        # Zentraler Frame für Eingabe, damit es mittig bleibt
        input_frame = tb.Frame(self)
        input_frame.grid(row=1, column=0, pady=10)

        # Da hinein kommt:
        # 1) "Hinzufügen"-Teil
        # 2) "Entfernen/Reduzieren"-Teil
        # => Wir verwenden grid in `input_frame`
        input_frame.columnconfigure(0, weight=1)
        input_frame.rowconfigure(0, weight=0)
        input_frame.rowconfigure(1, weight=0)

        # 1) Hinzufügen
        add_container = tb.Frame(input_frame)
        add_container.grid(row=0, column=0, pady=5, sticky="n")

        form_frame = tb.Frame(add_container)
        form_frame.grid(row=0, column=0, pady=5)

        lbl_ticker = tb.Label(form_frame, text="Ticker:")
        lbl_ticker.grid(row=0, column=0, padx=5, pady=2)
        self.ticker_entry = tb.Entry(form_frame, width=10)
        self.ticker_entry.grid(row=0, column=1, padx=5, pady=2)

        lbl_qty = tb.Label(form_frame, text="Anzahl:")
        lbl_qty.grid(row=0, column=2, padx=5, pady=2)
        self.quantity_entry = tb.Entry(form_frame, width=5)
        self.quantity_entry.grid(row=0, column=3, padx=5, pady=2)

        lbl_price = tb.Label(form_frame, text="Kaufpreis:")
        lbl_price.grid(row=0, column=4, padx=5, pady=2)
        self.price_entry = tb.Entry(form_frame, width=7)
        self.price_entry.grid(row=0, column=5, padx=5, pady=2)

        btn_add = tb.Button(
            add_container,
            text="Hinzufügen",
            command=self.add_ticker,
            bootstyle="success"
        )
        btn_add.grid(row=1, column=0, pady=5)

        # 2) Entfernen/Reduzieren
        rm_container = tb.Frame(input_frame)
        rm_container.grid(row=1, column=0, pady=10, sticky="n")

        rm_form_frame = tb.Frame(rm_container)
        rm_form_frame.grid(row=0, column=0, pady=5)

        lbl_rm_ticker = tb.Label(rm_form_frame, text="Ticker:")
        lbl_rm_ticker.grid(row=0, column=0, padx=5, pady=2)
        self.rm_ticker_entry = tb.Entry(rm_form_frame, width=10)
        self.rm_ticker_entry.grid(row=0, column=1, padx=5, pady=2)

        lbl_rm_qty = tb.Label(rm_form_frame, text="Reduzieren um:")
        lbl_rm_qty.grid(row=0, column=2, padx=5, pady=2)
        self.rm_quantity_entry = tb.Entry(rm_form_frame, width=5)
        self.rm_quantity_entry.grid(row=0, column=3, padx=5, pady=2)

        btn_reduce = tb.Button(
            rm_container,
            text="Reduzieren",
            command=self.reduce_quantity,
            bootstyle="danger"
        )
        btn_reduce.grid(row=1, column=0, pady=5, sticky="ew")

        btn_delete = tb.Button(
            rm_container,
            text="Ticker komplett löschen",
            command=self.delete_ticker,
            bootstyle="danger"
        )
        btn_delete.grid(row=2, column=0, pady=5, sticky="ew")

        # Portfolio-Anzeige in Zeile 2
        self.portfolio_frame = tb.Frame(self)
        self.portfolio_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        # expand
        self.rowconfigure(2, weight=1)

        self.update_portfolio()

    def on_theme_change(self):
        # Könntest ggf. Farben anpassen, aktuell nicht zwingend nötig
        pass

    def add_ticker(self):
        new_ticker = self.ticker_entry.get().strip().upper()
        qty_str = self.quantity_entry.get().strip()
        price_str = self.price_entry.get().strip()

        if not new_ticker or not qty_str or not price_str:
            messagebox.showwarning("Eingabe unvollständig", "Bitte alle Felder ausfüllen.")
            return
        if not qty_str.isdigit() or not self.is_float(price_str):
            messagebox.showerror("Ungültige Eingabe", "Anzahl/Preis ungültig!")
            return

        new_qty = int(qty_str)
        new_price = float(price_str)
        if new_qty <= 0 or new_price <= 0:
            messagebox.showerror("Ungültige Werte", "Anzahl und Preis müssen > 0 sein.")
            return

        try:
            self.app.db.save_item(new_ticker, new_qty, new_price)
            self.app.reload_portfolio_data()
            self.update_portfolio()
            dash = self.app.frames["DashboardPage"]
            dash.update_dashboard()
        except Exception as e:
            messagebox.showerror("DB-Fehler", f"Fehler beim Speichern:\n{e}")

        self.ticker_entry.delete(0, "end")
        self.quantity_entry.delete(0, "end")
        self.price_entry.delete(0, "end")

    def reduce_quantity(self):
        ticker = self.rm_ticker_entry.get().strip().upper()
        qty_str = self.rm_quantity_entry.get().strip()
        if not ticker:
            messagebox.showwarning("Fehlender Ticker", "Bitte Ticker eingeben.")
            return
        if not qty_str.isdigit():
            messagebox.showerror("Ungültige Eingabe", "Reduktionsmenge ungültig!")
            return

        qty = int(qty_str)
        if qty <= 0:
            messagebox.showerror("Ungültige Werte", "Reduktionsmenge muss > 0 sein.")
            return

        try:
            self.app.db.remove_or_reduce_item(ticker, quantity=qty)
            self.app.reload_portfolio_data()
            self.update_portfolio()

            dash = self.app.frames["DashboardPage"]
            dash.update_dashboard()
        except Exception as e:
            messagebox.showerror("DB-Fehler", f"Fehler beim Reduzieren:\n{e}")

        self.rm_ticker_entry.delete(0, "end")
        self.rm_quantity_entry.delete(0, "end")

    def delete_ticker(self):
        ticker = self.rm_ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Fehlender Ticker", "Bitte Ticker eingeben.")
            return

        try:
            self.app.db.remove_or_reduce_item(ticker, quantity=None)
            self.app.reload_portfolio_data()
            self.update_portfolio()

            dash = self.app.frames["DashboardPage"]
            dash.update_dashboard()
        except Exception as e:
            messagebox.showerror("DB-Fehler", f"Fehler beim Löschen:\n{e}")

        self.rm_ticker_entry.delete(0, "end")
        self.rm_quantity_entry.delete(0, "end")

    def update_portfolio(self):
        for widget in self.portfolio_frame.winfo_children():
            widget.destroy()

        if not self.app.portfolio_data:
            lbl_empty = tb.Label(
                self.portfolio_frame,
                text="Ihr Portfolio ist leer.",
                font=("Helvetica", 14)
            )
            lbl_empty.pack(pady=20)
        else:
            for item in self.app.portfolio_data:
                # neutrales Frame (kein info-Balken)
                card = tb.Frame(self.portfolio_frame, padding=10)
                card.pack(pady=5, fill="x")

                info_str = (
                    f"{item['ticker']} – "
                    f"{item['quantity']} Stück – "
                    f"Durchschn. Kaufpreis: {item['avg_price']:.2f} USD"
                )
                lbl_info = tb.Label(card, text=info_str, font=("Helvetica", 14, "bold"), anchor="w")
                lbl_info.pack(side="left")

    def is_float(self, val: str) -> bool:
        try:
            float(val)
            return True
        except ValueError:
            return False

    def stop_threads(self):
        pass


if __name__ == "__main__":
    app = App()
    app.mainloop()
