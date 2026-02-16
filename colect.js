// ==UserScript==
// @name         Aviator Collector - Multiplicador + Hora
// @namespace    Coordinated Flow v1
// @version      1.6.0
// @description  Coleta multiplicador + hora e salva no Realtime Database (sem duplicar)
// @match        https://aviator-next.spribegaming.com/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function () {
    'use strict';

    const INTERVALO = 2500;
    const TEMPO_MAX_COLETA_MS = 4500;

    // URL principal do RTDB (regional, conforme seu Firebase)
    const DB_BASE_URLS = [
        "https://multiplicadores-online-default-rtdb.europe-west1.firebasedatabase.app",
        "https://multiplicadores-online-default-rtdb.firebaseio.com"
    ];

    const DB_ROOT = "aviator";

    let rodando = false;
    let ultimaHora = null;
    let ultimoMultiplicador = null;

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function getByXPath(xpath, doc = document) {
        return doc.evaluate(
            xpath,
            doc,
            null,
            XPathResult.FIRST_ORDERED_NODE_TYPE,
            null
        ).singleNodeValue;
    }

    function clicar(el) {
        if (!el) return;
        el.dispatchEvent(new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    }

    function dataIsoLocal() {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, "0");
        const dd = String(now.getDate()).padStart(2, "0");
        return `${yyyy}-${mm}-${dd}`;
    }

    function montarDbUrl(baseUrl, path) {
        return `${baseUrl}/${path}.json`;
    }

    function extrairMultiplicador(texto) {
        if (!texto) return null;
        const limpo = texto.replace(/\s+/g, " ").trim();
        const m = limpo.match(/(\d+(?:[.,]\d+)?\s*x?)/i);
        if (!m) return null;
        return m[1].replace(/\s+/g, "").replace(',', '.').toLowerCase().endsWith('x')
            ? m[1].replace(/\s+/g, "").replace(',', '.')
            : `${m[1].replace(/\s+/g, "").replace(',', '.')}x`;
    }

    function extrairHora(texto) {
        if (!texto) return null;
        const limpo = texto.replace(/\s+/g, " ").trim();
        const m = limpo.match(/\b(\d{1,2}:\d{2}(?::\d{2})?)\b/);
        return m ? m[1] : limpo;
    }

    function buscarTextoPrimeiro(selectors) {
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const txt = (el.textContent || "").trim();
            if (txt) return txt;
        }
        return null;
    }

    async function coletarMultiplicadorEHora() {
        const multiplicadorSelectors = [
            ".bubble-multiplier.font-weight-bold",
            ".bubble-multiplier",
            "[class*='multiplier']"
        ];

        const horaSelectors = [
            ".header__info-time",
            "[class*='time']",
            "[class*='clock']"
        ];

        const inicio = Date.now();
        while (Date.now() - inicio < TEMPO_MAX_COLETA_MS) {
            const textoMultiplicador = buscarTextoPrimeiro(multiplicadorSelectors);
            const textoHora = buscarTextoPrimeiro(horaSelectors);

            const multiplicador = extrairMultiplicador(textoMultiplicador);
            const hora = extrairHora(textoHora);

            if (multiplicador && hora) {
                return { multiplicador, hora };
            }

            await sleep(120);
        }

        return null;
    }

    async function enviarParaRealtimeDB(multiplicador, hora) {
        const payload = `${multiplicador} - ${hora}`;
        const dia = dataIsoLocal();

        const erros = [];

        for (const baseUrl of DB_BASE_URLS) {
            try {
                const urlHistorico = montarDbUrl(baseUrl, `${DB_ROOT}/historico/${dia}`);
                const respHistorico = await fetch(urlHistorico, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                if (!respHistorico.ok) {
                    const texto = await respHistorico.text();
                    erros.push(`${respHistorico.status} historico ${baseUrl}: ${texto}`);
                    continue;
                }

                return;
            } catch (err) {
                erros.push(`rede ${baseUrl}: ${String(err)}`);
            }
        }

        throw new Error(`Falha ao salvar no RTDB: ${erros.join(" | ")}`);
    }

    function localizarBotaoAbrir() {
        return (
            getByXPath("/html/body/app-root/app-game/div/div/div[2]/div/div[2]/div[2]/app-stats-widget/div/div/div/div") ||
            document.querySelector("app-stats-widget div")
        );
    }

    function localizarBotaoFechar() {
        return (
            getByXPath("/html/body/ngb-modal-window/div/div/app-fairness/div/button/span") ||
            document.querySelector("ngb-modal-window app-fairness button") ||
            document.querySelector("ngb-modal-window button")
        );
    }

    async function ciclo() {
        if (rodando) return;
        rodando = true;

        try {
            const botaoAbrir = localizarBotaoAbrir();
            if (!botaoAbrir) {
                console.warn("Botao de abertura nao encontrado.");
                return;
            }

            clicar(botaoAbrir);
            await sleep(700);

            const dados = await coletarMultiplicadorEHora();
            if (!dados) {
                console.warn("Nao consegui ler multiplicador/hora neste ciclo.");
                return;
            }

            const { multiplicador, hora } = dados;

            if (hora === ultimaHora && multiplicador === ultimoMultiplicador) {
                console.log("Ignorado (repetido):", multiplicador, hora);
                return;
            }

            await enviarParaRealtimeDB(multiplicador, hora);
            ultimaHora = hora;
            ultimoMultiplicador = multiplicador;

            console.log("Salvo no RTDB:", `${multiplicador} - ${hora}`);
        } catch (e) {
            console.warn("Erro no ciclo:", e);
        } finally {
            await sleep(300);
            const botaoFechar = localizarBotaoFechar();
            if (botaoFechar) clicar(botaoFechar);
            rodando = false;
        }
    }

    setInterval(ciclo, INTERVALO);
    console.log("Aviator Collector iniciado (coleta robusta + RTDB)");
})();
