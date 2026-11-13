  return (...args) => construct(func, args);
}

/* Add properties to a lookup table */
export function addToSet(set, array, transformCaseFunc) {
  transformCaseFunc = transformCaseFunc ? transformCaseFunc : stringToLowerCase;
  if (setPrototypeOf) {
    // Make 'in' and truthy checks like Boolean(set.constructor)
    // independent of any properties defined on Object.prototype.
    // Prevent prototype setters from intercepting set as a this value.
    setPrototypeOf(set, null);
  }

  let l = array.length;
  while (l--) {
    let element = array[l];
    if (typeof element === 'string') {
      const lcElement = transformCaseFunc(element);
      if (lcElement !== element) {
        // Config presets (e.g. tags.js, attrs.js) are immutable.
        if (!isFrozen(array)) {
          array[l] = lcElement;
        }

        element = lcElement;
      }
    }

    set[element] = true;
  }

  return set;
}

/* Shallow clone an object */
export function clone(object) {
  const newObject = create(null);

  let property;
  for (property in object) {
    if (apply(hasOwnProperty, object, [property])) {
      newObject[property] = object[property];
    }
  }

  return newObject;
}

/* IE10 doesn't support __lookupGetter__ so lets'
 * simulate it. It also automatically checks
 * if the prop is function or getter and behaves
 * accordingly. */
function lookupGetter(object, prop) {
  while (object !== null) {
    const desc = getOwnPropertyDescriptor(object, prop);
    if (desc) {
      if (desc.get) {
        return unapply(desc.get);
      }

      if (typeof desc.value === 'function') {
        return unapply(desc.value);
      }
    }

    object = getPrototypeOf(object);
  }

  function fallbackValue(element) {
    console.warn('fallback value for', element);
    return null;
  }

  return fallbackValue;
}

export {
  // Array
  arrayForEach,
  arrayIndexOf,
  arrayPop,
