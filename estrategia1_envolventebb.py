import numpy as np
import pandas as pd
import talib as ta
import math
import yfinance as yf
import matplotlib.pyplot as plt
import datetime
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import matplotlib.dates as md
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.lib import SignalStrategy
import os
from dotenv import load_dotenv

load_dotenv()
years = int(os.environ['years'])
hoy = date.today()  # fecha de hoy
# fecha de comienzo en timeframe diario
comienzo = (hoy - relativedelta(years=years))

# DATOS DE .ENV
activo = os.environ['activo']
period = os.environ['period']
interval = os.environ['interval']
periodo_bb = int(os.environ['periodo_bb'])
riesgo_op = float(os.environ['riesgo_op'])
capital = int(os.environ['capital'])
comision = float(os.environ['comision'])
margen = float(os.environ['margen'])

#DATOS INTRADÍA YAHOO FINANCE
if interval=='1d' or interval=='1wk' or interval=='1mo':
    df = yf.download(tickers=activo, start=comienzo, end=hoy)
else:
    df = yf.download(tickers=activo, period=period, interval=interval)
    df=df.reset_index()
    df = df.rename({'index': 'Datetime'}, axis=1)
    df.index = pd.to_datetime(df['Datetime']).dt.strftime('%Y-%m-%d %H:%M:%S')
    df=df.drop(['Datetime'], axis=1)
df.index=pd.to_datetime(df.index)
df = df.iloc[:-1]

#INDICADORES
df['UBB'],df['MBB'],df['LBB'] = ta.BBANDS(df['Close'],periodo_bb)
df['envolvente']= ta.CDLENGULFING(df['Open'],df['High'],df['Low'],df['Close'])

#ACTIVAR ENTRADA
df['entrada']=0
for i in range(len(df)):
    if df['envolvente'][i]==100 and (df['Low'][i-1]<df['LBB'][i-1] or df['Low'][i]<df['LBB'][i]):
        df['entrada'][i]=100
    elif df['envolvente'][i]==-100 and (df['High'][i-1]>df['UBB'][i-1] or df['High'][i]>df['UBB'][i]):
        df['entrada'][i]=-100

#GESTIÓN DE STOPS           
df['pr_entrada']=0.0
df['stop']=0.0
df['posicion_c']=0
df['posicion_v']=0
df_=df
df_=df_.reset_index()

#inicial
for t in range(len(df)):
    if df['entrada'][t]==100:
        df['pr_entrada'][t]=df['Close'][t]
        stop_a = df_.loc[t-4:t, 'Low'].min()
        df['stop'][t]=stop_a
    elif df['entrada'][t]==-100:
        df['pr_entrada'][t]=df['Close'][t]
        stop_b = df_.loc[t-4:t, 'High'].max()
        df['stop'][t]=stop_b

df['stop'].replace(0, np.nan, inplace=True)
df['stop'].fillna(method='ffill', inplace=True)
df['stop'] = df['stop'].fillna(0)

#final
for x in range(len(df)):
    if df['Close'][x]>df['UBB'][x]:
        df['posicion_c'][x]=1
    if df['Low'][x]<df['MBB'][x]:
        df['posicion_c'][x]=-1
    if df['Close'][x]<df['LBB'][x]:
        df['posicion_v'][x]=2
    if df['High'][x]>df['MBB'][x]:
        df['posicion_v'][x]=-2
        
cols=['posicion_c','posicion_v']
df[cols].replace(0, np.nan, inplace=True)
df[cols].fillna(method='ffill', inplace=True)

#VOLUMEN A INVERTIR
df['contratos']=0
df=df.dropna()
for x in range(len(df)):
    if activo[-1]=='X': #en divisas
        if df['pr_entrada'][x]>0 :
            df['contratos'][x]=math.ceil(abs((riesgo_op*capital)/(df['pr_entrada'][x]-df['stop'][x])*0.00001)) 
    else:
        if df['pr_entrada'][x]>0 :
            df['contratos'][x]=math.ceil(abs((riesgo_op*capital)/(df['pr_entrada'][x]-df['stop'][x])))
            
#DEFINIMOS EL BACKTEST
class estrategia1(SignalStrategy):

    def init(self):
        super().init()
        
    def next(self):
        super().next()
        pr_entrada = self.data.pr_entrada
        entrada=self.data.entrada
        contratos=self.data.contratos
        media=self.data.MBB
        stop=self.data.stop
        if entrada==100 and pr_entrada>0:
            alcista=contratos[np.argwhere((entrada==100) & (pr_entrada>0))[-1]]
            self.buy(size=alcista[0])
        if entrada==-100 and pr_entrada>0:
            bajista=contratos[np.argwhere((entrada==-100) & (pr_entrada>0))[-1]]
            self.sell(size=bajista[0])            
        for trade in self.trades:
            if trade.is_long:
                trade.sl=stop
                if self.data.posicion_c==1:
                    trade.sl = media
            if trade.is_short:
                trade.sl=stop
                if self.data.posicion_v==2:
                    trade.sl = media

btest = Backtest(df, estrategia1, cash=capital, commission=comision, exclusive_orders=False, hedging=True, trade_on_close=False, margin=margen)
stats=btest.run()
btest.plot(open_browser=False)

resultados={}
rentabilidad=round(stats[6],2)
n_operaciones=stats[17]
ratio_aciertos=round(stats[18],2)
drawdown=round(stats[13],2)
resultados={'Rentabilidad':rentabilidad, 'Número de operaciones':n_operaciones, 'Ratio de aciertos (%)':ratio_aciertos, 'Máximo Dradown (%)':drawdown}
df_resultados = pd.DataFrame(resultados,index=['Estrategia Nº1'])
print(df_resultados)
