DEFAULT_USER = "Sistema"

MESSAGES = {
    "siren": {
        "on": "{user} ha abilitato la sirena",
        "off": "{user} ha disabilitato la sirena",
        "error": "Errore nell'azionamento della sirena richiesta da {user}",
    },
    "pump": {
        "on": "{user} ha attivato la pompa",
        "off": "{user} ha disattivato la pompa",
        "error": "Errore nell'azionamento della pompa richiesta da {user}",
    },
    "reset_statistics": {
        "success": "Contatori resettati da {user}",
    },
}

ALARM_MESSAGES = {
    "triggered": "ALLARME CISTERNA: Livello acqua troppo alto! Intervenire immediatamente.",
    "cleared": "Allarme cisterna rientrato: il livello dell'acqua è tornato nella norma.",
}

STATUS_DESCRIPTIONS = {
    "0": "disattivo",
    "1": "attivo",
    "unknown": "sconosciuto",
}
