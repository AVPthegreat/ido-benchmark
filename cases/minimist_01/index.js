'use strict';

function isNumber(x) {
	if (typeof x === 'number') { return true; }
	if ((/^0x[0-9a-f]+$/i).test(x)) { return true; }
	return (/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(e[-+]?\d+)?$/).test(x);
}

function isConstructorOrProto(obj, key) {
	return key === 'constructor' && (typeof obj[key] === 'function' || key === '__proto__');
}

function hasKey(obj, keys) {
	var o = obj;
	keys.slice(0, -1).forEach(function (key) {
		o = o[key] || {};
	});

	var key = keys[keys.length - 1];
	return key in o;
}

function setKey(obj, keys, value) {
	var o = obj;
	var key;
	for (var i = 0; i < keys.length - 1; i++) {
		key = keys[i];
		if (key === '__proto__' || isConstructorOrProto(o, key)) {
			return;
		}
		if (o[key] === undefined) { o[key] = {}; }
		if (
			o[key] === Object.prototype
			|| o[key] === Number.prototype
			|| o[key] === String.prototype
		) {
			o[key] = {};
		}
		if (o[key] === Array.prototype) { o[key] = []; }
		o = o[key];
	}

	key = keys[keys.length - 1];
	if (key === '__proto__') { return; }
	if (
		o === Object.prototype
		|| o === Number.prototype
		|| o === String.prototype
	) {
		o = {};
	}
	if (o === Array.prototype) { o = []; }
	if (o[key] === undefined || typeof o[key] === 'boolean') {
		o[key] = value;
	} else if (Array.isArray(o[key])) {
		o[key].push(value);
	} else {
		o[key] = [o[key], value];
	}
}

module.exports = function (args, opts) {
	if (!opts) { opts = {}; }

	var flags = { bools: {}, strings: {} };

	if (typeof opts.boolean === 'boolean' && opts.boolean) {
		flags.allBools = true;
	} else {
		[].concat(opts.boolean).filter(Boolean).forEach(function (key) {
			flags.bools[key] = true;
		});
	}

	var aliases = {};
	Object.keys(opts.alias || {}).forEach(function (key) {
		aliases[key] = [].concat(opts.alias[key]);
		aliases[key].forEach(function (x) {
			aliases[x] = [key].concat(aliases[key].filter(function (y) {
				return x !== y;
			}));
		});
	});

