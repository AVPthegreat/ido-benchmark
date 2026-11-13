                    function (encodedVal) {
                        return options.decoder(encodedVal, defaults.decoder, charset, 'value');
                    }
                );
            }
        }

        if (val && options.interpretNumericEntities && charset === 'iso-8859-1') {
            val = utils.maybeMap(val, function (value) {
                return value ? interpretNumericEntities(String(value)) : value;
            });
        }

        if (isEmptyBracketKey) {
            val = isArray(val) ? [val] : val;
        }

        if (options.comma && isArray(val) && val.length > options.arrayLimit) {
            val = utils.combine([], val, options.arrayLimit, options.plainObjects, options.throwOnLimitExceeded);
        }

        if (key !== null) {
            var existing = has.call(obj, key);
            if (existing && (options.duplicates === 'combine' || isEmptyBracketKey)) {
                obj[key] = utils.combine(
                    obj[key],
                    val,
                    options.arrayLimit,
                    options.plainObjects,
                    options.throwOnLimitExceeded
                );
            } else if (!existing || options.duplicates === 'last') {
                obj[key] = val;
            }
        }
    }

    return obj;
};

var stripWrappingBrackets = function stripWrappingBrackets(key) {
    return key.charAt(0) === '[' && key.charAt(key.length - 1) === ']' ? key.slice(1, -1) : key;
};

var parseObject = function (chain, val, options, valuesParsed) {
    var currentArrayLength = 0;
    if (chain.length > 0 && chain[chain.length - 1] === '[]') {
        var parentKey = chain.slice(0, -1).join('');
        currentArrayLength = Array.isArray(val) && val[parentKey] ? val[parentKey].length : 0;
    }

    var leaf = valuesParsed ? val : parseArrayValue(val, options, currentArrayLength);

    for (var i = chain.length - 1; i >= 0; --i) {
        var obj;
        var root = chain[i];

        if (root === '[]' && options.parseArrays) {
            if (utils.isOverflow(leaf)) {
                // leaf is already an overflow object, preserve it
                obj = leaf;
            } else {
                obj = options.allowEmptyArrays && (leaf === '' || (options.strictNullHandling && leaf === null))
                    ? []
                    : utils.combine(
                        [],
                        leaf,
                        options.arrayLimit,
                        options.plainObjects,
                        options.throwOnLimitExceeded
                    );
            }
        } else {
            obj = options.plainObjects ? { __proto__: null } : {};
            var cleanRoot = stripWrappingBrackets(root);
            var decodedRoot = options.decodeDotInKeys ? cleanRoot.replace(/%2E/gi, '.') : cleanRoot;
            var index = parseInt(decodedRoot, 10);
            var isValidArrayIndex = !isNaN(index)
                && root !== decodedRoot
                && String(index) === decodedRoot
                && index >= 0
                && options.parseArrays;
            if (!options.parseArrays && decodedRoot === '') {
                obj = { 0: leaf };
            } else if (isValidArrayIndex && index < options.arrayLimit) {
                obj = [];
                obj[index] = leaf;
            } else if (isValidArrayIndex && options.throwOnLimitExceeded) {
                throw new RangeError('Array limit exceeded. Only ' + options.arrayLimit + ' element' + (options.arrayLimit === 1 ? '' : 's') + ' allowed in an array.');
            } else if (isValidArrayIndex) {
                obj[index] = leaf;
                utils.markOverflow(obj, index);
            } else if (decodedRoot !== '__proto__') {
                obj[decodedRoot] = leaf;
            }
        }

        leaf = obj;
    }

    return leaf;
};

// Behaves like `key.replace(/\.([^.[]+)/g, '[$1]')`, but only rewrites a dot
// that sits at bracket depth 0. A literal dot already inside a `[...]` segment
// is left untouched instead of corrupting the key (e.g. "outer[a.b]"). (#617)
var topLevelDotsToBrackets = function topLevelDotsToBrackets(key) {
    var result = '';
    var depth = 0;
    for (var i = 0; i < key.length; i += 1) {
        var cu = key.charCodeAt(i);
        if (cu === 0x5B) { // '['
            depth += 1;
            result += '[';
        } else if (cu === 0x5D) { // ']'
