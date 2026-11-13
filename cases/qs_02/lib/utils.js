        return target;
    }

    return Object.keys(source).reduce(function (acc, key) {
        var value = source[key];

        if (has.call(acc, key)) {
            setProperty(acc, key, merge(acc[key], value, options));
        } else {
            setProperty(acc, key, value);
        }

        if (isOverflow(source) && !isOverflow(acc)) {
            markOverflow(acc, maxNumericIndex(acc, getMaxIndex(source)));
        }
        if (isOverflow(acc)) {
            var keyNum = parseInt(key, 10);
            if (String(keyNum) === key && keyNum >= 0 && keyNum > getMaxIndex(acc)) {
                setMaxIndex(acc, keyNum);
            }
        }
        if (isConflict(acc)) {
            var conflictKey = parseInt(key, 10);
            if (String(conflictKey) === key && conflictKey > getConflictIndex(acc)) {
                markConflict(acc, conflictKey);
            }
        }

        return acc;
    }, mergeTarget);
};

var assign = function assignSingleSource(target, source) {
    return Object.keys(source).reduce(function (acc, key) {
        setProperty(acc, key, source[key]);
        return acc;
    }, target);
};

var decode = function (str, defaultDecoder, charset) {
    var strWithoutPlus = str.replace(/\+/g, ' ');
    if (charset === 'iso-8859-1') {
        // unescape never throws, no try...catch needed:
        return strWithoutPlus.replace(/%[0-9a-f]{2}/gi, unescape);
    }
    // utf-8
    try {
        return decodeURIComponent(strWithoutPlus);
    } catch (e) {
        return strWithoutPlus;
    }
};

var hasToPrimitive = typeof Symbol === 'function' && typeof Symbol.toPrimitive === 'symbol';
var arrayJoin = Array.prototype.join;
var arrayToString = Array.prototype.toString;
var objectToString = Object.prototype.toString;

// an object with no callable toString (eg, from JSON, or null-prototype) would make String() or join() throw,
// so it becomes its primitive valueOf or else Object.prototype.toString; arrays are walked like join walks them,
// copied only once an element changes, with an array already being joined becoming '' as engines do for cycles
var toCoercible = function toCoercible(value, joining) {
    if (!value || (typeof value !== 'object' && typeof value !== 'function')) {
        return value;
    }
    if (hasToPrimitive && value[Symbol.toPrimitive] != null) {
        return value;
    }
    if (isArray(value) && value.toString === arrayToString && value.join === arrayJoin) {
        var ancestors = joining || getSideChannel();
        if (ancestors.has(value)) {
            return '';
        }
        ancestors.set(value, true);
        var copy;
        for (var i = 0; i < value.length; i += 1) {
            var item = value[i];
            var coerced = toCoercible(item, ancestors);
            if (!copy && coerced !== item) {
                copy = [];
