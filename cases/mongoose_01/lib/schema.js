 *
 * [Plugins](https://mongoosejs.com/docs/plugins.html) can use the return value of this function to modify a schema's indexes.
 * For example, the below plugin makes every index unique by default.
 *
 *     function myPlugin(schema) {
 *       for (const index of schema.indexes()) {
 *         if (index[1].unique === undefined) {
 *           index[1].unique = true;
 *         }
 *       }
 *     }
 *
 * @api public
 * @return {Array} list of indexes defined in the schema
 */

Schema.prototype.indexes = function() {
  return getIndexes(this);
};

/**
 * Creates a virtual type with the given name.
 *
 * @param {String} name The name of the Virtual
 * @param {Object} [options]
 * @param {String|Model} [options.ref] model name or model instance. Marks this as a [populate virtual](https://mongoosejs.com/docs/populate.html#populate-virtuals).
 * @param {String|Function} [options.localField] Required for populate virtuals. See [populate virtual docs](https://mongoosejs.com/docs/populate.html#populate-virtuals) for more information.
 * @param {String|Function} [options.foreignField] Required for populate virtuals. See [populate virtual docs](https://mongoosejs.com/docs/populate.html#populate-virtuals) for more information.
 * @param {Boolean|Function} [options.justOne=false] Only works with populate virtuals. If [truthy](https://masteringjs.io/tutorials/fundamentals/truthy), will be a single doc or `null`. Otherwise, the populate virtual will be an array.
 * @param {Boolean} [options.count=false] Only works with populate virtuals. If [truthy](https://masteringjs.io/tutorials/fundamentals/truthy), this populate virtual will contain the number of documents rather than the documents themselves when you `populate()`.
 * @param {Function|null} [options.get=null] Adds a [getter](https://mongoosejs.com/docs/tutorials/getters-setters.html) to this virtual to transform the populated doc.
 * @param {Object|Function} [options.match=null] Apply a default [`match` option to populate](https://mongoosejs.com/docs/populate.html#match), adding an additional filter to the populate query.
 * @param {Boolean} [options.applyToArray=false] If true and the given `name` is a direct child of an array, apply the virtual to the array rather than the elements.
 * @return {VirtualType}
 */

Schema.prototype.virtual = function(name, options) {
  if (name instanceof VirtualType || getConstructorName(name) === 'VirtualType') {
    return this.virtual(name.path, name.options);
  }
  const parts = name.split('.');
  for (const part of parts) {
    if (utils.specialProperties.has(part)) {
      throw new MongooseError('Cannot set special property `' + part + '` on a schema');
    }
  }
  options = new VirtualOptions(options);

  if (utils.hasUserDefinedProperty(options, ['ref', 'refPath'])) {
    if (options.localField == null) {
      throw new Error('Reference virtuals require `localField` option');
    }

    if (options.foreignField == null) {
      throw new Error('Reference virtuals require `foreignField` option');
    }

    const virtual = this.virtual(name);
    virtual.options = options;

    this.pre('init', function virtualPreInit(obj, opts) {
      if (mpath.has(name, obj)) {
        const _v = mpath.get(name, obj);
        if (!this.$$populatedVirtuals) {
          this.$$populatedVirtuals = {};
        }

        if (options.justOne || options.count) {
          this.$$populatedVirtuals[name] = Array.isArray(_v) ?
            _v[0] :
            _v;
        } else {
          this.$$populatedVirtuals[name] = Array.isArray(_v) ?
            _v :
            _v == null ? [] : [_v];
        }

        if (opts?.hydratedPopulatedDocs && !options.count) {
          const modelNames = virtual._getModelNamesForPopulate(this);
          const populatedVal = this.$$populatedVirtuals[name];
          if (!Array.isArray(populatedVal) && !populatedVal.$__ && modelNames?.length === 1) {
            const PopulateModel = this.db.model(modelNames[0]);
            this.$$populatedVirtuals[name] = PopulateModel.hydrate(populatedVal);
          } else if (Array.isArray(populatedVal) && modelNames?.length === 1) {
            const PopulateModel = this.db.model(modelNames[0]);
            for (let i = 0; i < populatedVal.length; ++i) {
              if (!populatedVal[i].$__) {
                populatedVal[i] = PopulateModel.hydrate(populatedVal[i], null, { hydratedPopulatedDocs: true });
              }
            }
            const foreignField = options.foreignField;
            this.$populated(
              name,
              populatedVal.map(doc => doc == null ? doc : doc.get(typeof foreignField === 'function' ? foreignField.call(doc, doc) : foreignField)),
              { populateModelSymbol: PopulateModel }
            );
          }
        }

        mpath.unset(name, obj);
      }
    });

    virtual.
      set(function(v) {
        if (!this.$$populatedVirtuals) {
          this.$$populatedVirtuals = {};
        }

        return setPopulatedVirtualValue(
          this.$$populatedVirtuals,
          name,
          v,
          options
        );
      });

    if (typeof options.get === 'function') {
      virtual.get(options.get);
    }

    // Workaround for gh-8198: if virtual is under document array, make a fake
    // virtual. See gh-8210, gh-13189
    const parts = name.split('.');
    let cur = parts[0];
    for (let i = 0; i < parts.length - 1; ++i) {
      if (this.paths[cur] == null) {
        continue;
      }

      if (this.paths[cur].$isMongooseDocumentArray || this.paths[cur].$isSingleNested) {
        const remnant = parts.slice(i + 1).join('.');
        this.paths[cur].schema.virtual(remnant, options);
        break;
      } else if (this.paths[cur].$isSchemaMap) {
        const remnant = parts.slice(i + 2).join('.');
        this.paths[cur].$__schemaType.schema.virtual(remnant, options);
        break;
      }

      cur += '.' + parts[i + 1];
    }

    return virtual;
  }

  const virtuals = this.virtuals;

  if (this.pathType(name) === 'real') {
    throw new Error('Virtual path "' + name + '"' +
      ' conflicts with a real path in the schema');
  }

  virtuals[name] = parts.reduce(function(mem, part, i) {
    mem[part] || (mem[part] = (i === parts.length - 1)
      ? new VirtualType(options, name)
      : {});
    return mem[part];
  }, this.tree);

  if (options && options.applyToArray && parts.length > 1) {
    const path = this.path(parts.slice(0, -1).join('.'));
    if (path && path.$isMongooseArray) {
      return path.virtual(parts[parts.length - 1], options);
    } else {
      throw new MongooseError(`Path "${path}" is not an array`);
    }
  }

  return virtuals[name];
};

/**
 * Returns the virtual type with the given `name`.
 *
 * @param {String} name The name of the Virtual to get
 * @return {VirtualType|null}
 */

Schema.prototype.virtualpath = function(name) {
  return Object.hasOwn(this.virtuals, name) ? this.virtuals[name] : null;
};

/**
 * Removes the given `path` (or [`paths`]).
 *
 * #### Example:
