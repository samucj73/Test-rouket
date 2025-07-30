def extrair_features(historico):
    historico = list(historico)
    X = []

    def cor(n):
        if n == 0:
            return 'G'
        return 'R' if n in [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36] else 'B'

    for i in range(60, len(historico)):
        ultimos = historico[i - 60:i]
        entrada = []

        # Frequência de dúzia e coluna (últimos 10 e 20)
        for janela in [10, 20]:
            d_freq = [0, 0, 0]
            c_freq = [0, 0, 0]
            for n in ultimos[-janela:]:
                if n == 0:
                    continue
                d = ((n - 1) // 12)
                c = ((n - 1) % 3)
                d_freq[d] += 1
                c_freq[c] += 1
            entrada += d_freq + c_freq

        # Frequência cor (R, B, G)
        cores = {'R': 0, 'B': 0, 'G': 0}
        for n in ultimos[-20:]:
            cores[cor(n)] += 1
        entrada += [cores['R'], cores['B'], cores['G']]

        # Par / ímpar
        par = sum(1 for n in ultimos[-20:] if n != 0 and n % 2 == 0)
        impar = 20 - par
        entrada += [par, impar]

        # Alta / baixa
        alta = sum(1 for n in ultimos[-20:] if n > 18)
        baixa = sum(1 for n in ultimos[-20:] if 0 < n <= 18)
        entrada += [alta, baixa]

        # Últimos 5 números brutos
        entrada += ultimos[-5:]

        # Diferenças entre últimos números
        for j in range(-5, -1):
            entrada.append(ultimos[j] - ultimos[j - 1])

        X.append(entrada)
    return np.array(X)

def treinar_modelos(historico):
    if len(historico) < 80:
        return None, None

    X = extrair_features(historico)
    y = list(historico)[60:]

    y_duzia = [((n - 1) // 12) + 1 if n != 0 else 0 for n in y]
    y_coluna = [((n - 1) % 3) + 1 if n != 0 else 0 for n in y]

    X_filtrado = []
    y_duzia_f = []
    y_coluna_f = []
    for xi, d, c in zip(X, y_duzia, y_coluna):
        if d > 0 and c > 0:
            X_filtrado.append(xi)
            y_duzia_f.append(d)
            y_coluna_f.append(c)

    modelo_duzia = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)
    modelo_coluna = RandomForestClassifier(n_estimators=200, class_weight='balanced', random_state=42)

    modelo_duzia.fit(X_filtrado, y_duzia_f)
    modelo_coluna.fit(X_filtrado, y_coluna_f)

    joblib.dump(modelo_duzia, MODELO_DUZIA_PATH)
    joblib.dump(modelo_coluna, MODELO_COLUNA_PATH)

    return modelo_duzia, modelo_coluna

def prever_proxima(modelo, historico, prob_minima=0.60):
    if len(historico) < 80:
        return None, 0.0

    X = extrair_features(historico)
    x = X[-1].reshape(1, -1)

    try:
        probas = modelo.predict_proba(x)[0]
        classe = np.argmax(probas) + 1
        prob = probas[classe - 1]
        if prob >= prob_minima:
            return classe, prob
        return None, prob
    except Exception as e:
        print(f"Erro previsão: {e}")
        return None, 0.0
