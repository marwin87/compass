// Constants the server writes into a page at the `/*I18N*/` marker (see `core.inject` in src/compass/ui/core.py).
declare const I18N: {
    lang: string;
    strings: Record<string, string>;
    callouts: Record<string, Record<string, string>>;
};
declare const SETTINGS: Record<string, any>;
declare const AI_READY: boolean;
