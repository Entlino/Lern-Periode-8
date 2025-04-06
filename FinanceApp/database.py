import sqlite3
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)


class Database:
    def __init__(self, db_path: str = "portfolio.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        logger.debug("Starte init_db()")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    ticker TEXT PRIMARY KEY,
                    quantity INTEGER NOT NULL,
                    avg_price REAL NOT NULL
                )
            """)
            conn.commit()
            logger.info("Tabelle 'portfolio' sichergestellt.")
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Erstellen der Tabelle: {e}")
            raise
        finally:
            conn.close()

    def load_portfolio(self) -> List[Dict[str, float]]:
        logger.debug("Starte load_portfolio()")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT ticker, quantity, avg_price FROM portfolio")
            rows = c.fetchall()
            logger.info(f"{len(rows)} Einträge aus 'portfolio' geladen.")
            portfolio_data = []
            for row in rows:
                ticker, quantity, avg_price = row
                portfolio_data.append({
                    "ticker": ticker,
                    "quantity": quantity,
                    "avg_price": avg_price
                })
            return portfolio_data
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Laden des Portfolios: {e}")
            raise
        finally:
            conn.close()

    def save_item(self, ticker: str, quantity: int, price: float):
        logger.debug(f"save_item(ticker={ticker}, quantity={quantity}, price={price})")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            c.execute("SELECT ticker, quantity, avg_price FROM portfolio WHERE ticker = ?", (ticker,))
            row = c.fetchone()

            if row is None:
                c.execute(
                    "INSERT INTO portfolio (ticker, quantity, avg_price) VALUES (?, ?, ?)",
                    (ticker, quantity, price)
                )
                logger.info(f"Neuer Ticker eingefügt: {ticker}, qty={quantity}, price={price}")
            else:
                _, old_qty, old_price = row
                total_cost_old = old_qty * old_price
                total_cost_new = quantity * price
                total_qty = old_qty + quantity
                new_avg_price = (total_cost_old + total_cost_new) / total_qty

                c.execute(
                    "UPDATE portfolio SET quantity = ?, avg_price = ? WHERE ticker = ?",
                    (total_qty, new_avg_price, ticker)
                )
                logger.info(f"Ticker aktualisiert: {ticker}, neue qty={total_qty}, avg_price={new_avg_price:.2f}")

            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Speichern des Tickers {ticker}: {e}")
            raise
        finally:
            conn.close()

    def remove_or_reduce_item(self, ticker: str, quantity: int = None):
        logger.debug(f"remove_or_reduce_item(ticker={ticker}, quantity={quantity})")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()

            if quantity is None:
                c.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker,))
                logger.info(f"Ticker {ticker} komplett gelöscht.")
            else:
                c.execute("SELECT ticker, quantity, avg_price FROM portfolio WHERE ticker = ?", (ticker,))
                row = c.fetchone()
                if row:
                    _, old_qty, old_price = row
                    new_qty = old_qty - quantity
                    if new_qty <= 0:
                        c.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker,))
                        logger.info(f"Ticker {ticker} entfernt, new_qty={new_qty} <= 0.")
                    else:
                        c.execute("UPDATE portfolio SET quantity = ? WHERE ticker = ?", (new_qty, ticker))
                        logger.info(f"Ticker {ticker} reduziert: alt={old_qty}, neu={new_qty}.")

            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Fehler beim Entfernen/Reduzieren des Tickers {ticker}: {e}")
            raise
        finally:
            conn.close()
