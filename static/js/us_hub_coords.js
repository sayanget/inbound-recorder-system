/**
 * US hub / airport coordinates for route codes (3-letter IATA-style).
 * Used by /route-map — extend when new destinations appear in 流向分布.
 */
(function (global) {
    const H = {
        CNO: { lat: 34.0122, lng: -117.6889, name: 'Chino (CNO 枢纽)' },
        LAV: { lat: 33.9425, lng: -118.4081, name: 'Los Angeles (LAV)' },
        LAX: { lat: 33.9425, lng: -118.4081, name: 'Los Angeles (LAX)' },
        IAH: { lat: 29.9844, lng: -95.3414, name: 'Houston (IAH)' },
        MCO: { lat: 28.4312, lng: -81.3081, name: 'Orlando (MCO)' },
        MIA: { lat: 25.7959, lng: -80.2870, name: 'Miami (MIA)' },
        ATL: { lat: 33.6407, lng: -84.4277, name: 'Atlanta (ATL)' },
        ATLG: { lat: 33.6407, lng: -84.4277, name: 'Atlanta (ATLG)' },
        DFW: { lat: 32.8998, lng: -97.0403, name: 'Dallas (DFW)' },
        ORD: { lat: 41.9742, lng: -87.9073, name: 'Chicago (ORD)' },
        CVG: { lat: 39.0489, lng: -84.6619, name: 'Cincinnati (CVG)' },
        EWR: { lat: 40.6895, lng: -74.1745, name: 'Newark (EWR)' },
        JFK: { lat: 40.6413, lng: -73.7781, name: 'New York (JFK)' },
        CLT: { lat: 35.2144, lng: -80.9473, name: 'Charlotte (CLT)' },
        SFO: { lat: 37.6213, lng: -122.3790, name: 'San Francisco (SFO)' },
        SEA: { lat: 47.4502, lng: -122.3088, name: 'Seattle (SEA)' },
        DEN: { lat: 39.8561, lng: -104.6737, name: 'Denver (DEN)' },
        MOD: { lat: 37.6391, lng: -120.9969, name: 'Modesto (MOD)' },
        PHX: { lat: 33.4352, lng: -112.0101, name: 'Phoenix (PHX)' },
        LAS: { lat: 36.0840, lng: -115.1537, name: 'Las Vegas (LAS)' },
        SJU: { lat: 18.4394, lng: -66.0018, name: 'San Juan (SJU)' },
        IND: { lat: 39.7173, lng: -86.2944, name: 'Indianapolis (IND)' },
        PHL: { lat: 39.8744, lng: -75.2424, name: 'Philadelphia (PHL)' },
        BOS: { lat: 42.3656, lng: -71.0096, name: 'Boston (BOS)' },
        MSP: { lat: 44.8848, lng: -93.2223, name: 'Minneapolis (MSP)' },
        SAN: { lat: 32.7338, lng: -117.1933, name: 'San Diego (SAN)' },
        PDX: { lat: 45.5898, lng: -122.5951, name: 'Portland (PDX)' },
        TPA: { lat: 27.9755, lng: -82.5332, name: 'Tampa (TPA)' },
        BNA: { lat: 36.1245, lng: -86.6782, name: 'Nashville (BNA)' },
        STL: { lat: 38.7487, lng: -90.3700, name: 'St. Louis (STL)' },
        OAK: { lat: 37.7126, lng: -122.2197, name: 'Oakland (OAK)' },
        RNO: { lat: 39.4991, lng: -119.7681, name: 'Reno (RNO)' },
        ABQ: { lat: 35.0402, lng: -106.6091, name: 'Albuquerque (ABQ)' },
        SAT: { lat: 29.5337, lng: -98.4698, name: 'San Antonio (SAT)' },
        AUS: { lat: 30.1975, lng: -97.6664, name: 'Austin (AUS)' },
        MEM: { lat: 35.0424, lng: -89.9767, name: 'Memphis (MEM)' },
        DTW: { lat: 42.2124, lng: -83.3534, name: 'Detroit (DTW)' },
        CLE: { lat: 41.4117, lng: -81.8498, name: 'Cleveland (CLE)' },
        PIT: { lat: 40.4915, lng: -80.2329, name: 'Pittsburgh (PIT)' },
        RDU: { lat: 35.8776, lng: -78.7875, name: 'Raleigh (RDU)' },
        ONT: { lat: 34.0560, lng: -117.6012, name: 'Ontario (ONT)' },
        BWI: { lat: 39.1774, lng: -76.6684, name: 'Baltimore (BWI)' },
        DCA: { lat: 38.8512, lng: -77.0402, name: 'Washington (DCA)' },
        IAD: { lat: 38.9531, lng: -77.4565, name: 'Washington (IAD)' },
        SLC: { lat: 40.7884, lng: -111.9778, name: 'Salt Lake City (SLC)' },
        HNL: { lat: 21.3187, lng: -157.9225, name: 'Honolulu (HNL)' },
        ANC: { lat: 61.1744, lng: -149.9963, name: 'Anchorage (ANC)' },
        TUC: { lat: 32.1161, lng: -110.9410, name: 'Tucson (TUC)' },
    };

    const ALIASES = {
        LAX: 'LAV',
        ATLG: 'ATL',
        TUC: 'PHX',
    };

    function resolveHub(code) {
        if (!code) return null;
        const u = String(code).toUpperCase().trim();
        if (u === 'UNKNOWN') return null;
        const key = ALIASES[u] || u;
        if (H[key]) return { code: u, ...H[key] };
        if (u.length >= 3 && H[u.slice(0, 3)]) {
            const k = u.slice(0, 3);
            return { code: u, ...H[k] };
        }
        return null;
    }

    global.US_HUB_COORDS = H;
    global.resolveUsHub = resolveHub;
})(typeof window !== 'undefined' ? window : globalThis);
