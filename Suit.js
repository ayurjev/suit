
var Suit = function() {

    this.connect = function(p1, p2, p3, p4) {
        var initiator_selector = p1;
        var event_name = p2;
        var cb;
        var subscriber;
        if (p4 == undefined) { cb = p3; subscriber = $("body"); }
        else { cb = p4; subscriber = p3; }
        if (subscriber.jquery) {
            subscriber.on(event_name, initiator_selector, cb);
        }
        else {
            if (initiator_selector.on) {
                initiator_selector.on(event_name, cb, subscriber);
            } else {
                throw new Error("there is no method 'on' in object '" + initiator_selector + "'");
            }
        }
    };

    /**
     * Makes a query to the backend with ajax-query
     *
     * @param url                       URL of the controller
     * @param data                      Request data
     * @param cb                        Callback function
     * @param error_suppression         Callback function for error suppression
     */
    this.ajax = function(url, data, cb, error_suppression) {
        var responseData = {};
        $.ajax({
            url:        url,
            async:      !!cb,
            type:       "POST",
            dataType:   "json",
            data:       {json: JSON.stringify(data)}
        })
        .done(function(data){ responseData = data; })
        .done(function(data) {
                if (cb && cb(data) !== false && (!error_suppression || error_suppression(data) !== true))
                suit.events_controller.broadcast("XHR_Request_Completed", data, error_suppression)})
        .fail(function() { suit.events_controller.broadcast("UnknownError") });
        return responseData;
    };

    /**
     * Makes a query to the backend with pjax-query
     * @param container Container for binding callbacks (execution context)
     * @param url       URL of the controller
     * @param data      Request data
     * @param cb        Callback function
     * @param timeout   Execution timeout
     */
    this.pjax = function(container, url, data, cb, timeout) {

        if (!$(container).data("success.pjax.binded")) {
            $(container).bind("success.pjax", function(event, data) {suit.events_controller.broadcast("XHR_Request_Completed", data); return cb(data)});
            $(container).bind("error.pjax", function(jqXHR, textStatus, errorThrown) {suit.events_controller.broadcast("UnknownError", jqXHR, textStatus, errorThrown);});
            $(container).data("success.pjax.binded", true);
        }
        $.pjax({
            url: url,
            container: container,
            data: data,
            type: "POST",
            dataType: "json",
            timeout: timeout || 3000
        });
    };

    /**
     * Events Manager
     */
    this.EventsController = function() {
        var internal = {};
        internal.eventsHandlers = {};
        internal.on = function(eventName, cb, subscriber) {
            if (!internal.eventsHandlers[eventName]) { internal.eventsHandlers[eventName] = []; }
            internal.eventsHandlers[eventName].push({"subscriber": subscriber, "cb": cb});
        };
        internal.broadcast = function(eventName, data) {
            if (internal.eventsHandlers[eventName]) {
                for (var i=0; i < internal.eventsHandlers[eventName].length; i++) {
                    var subscriber = internal.eventsHandlers[eventName][i]["subscriber"];
                    var cb = internal.eventsHandlers[eventName][i]["cb"];
                    if (subscriber && $(subscriber).length == 0) { }
                    else { cb(data); }
                }
            }
        };
        return { "on": internal.on, "broadcast": internal.broadcast }
    };

    this.ErrorController = function() {
        var internal = {};
        internal.eventsController = new suit.EventsController();
        internal.unknownExceptionHandler = false;
        internal.knownExceptions = {};
        internal.on = function(error_type, cb) {
            if (error_type == "*") {
                internal.unknownExceptionHandler = cb;
            } else {
                internal.knownExceptions[error_type] = true;
                internal.eventsController.on(error_type, cb);
            }
        };
        internal.broadcast = function(error) {
            internal.eventsController.broadcast(error.error_type, error.error_data);
            if (!internal.knownExceptions[error.error_type]) {
                if (internal.unknownExceptionHandler) {
                    internal.unknownExceptionHandler(error.error_data);
                }
            }
        };
        return { "on": internal.on, "broadcast": internal.broadcast };

    };

    /**
     * Some usefull utils
     */
    this.utils = {
        "pluralForm": function(initial_num, words) {
            var num = parseInt(initial_num) % 100;
            var word;
            if (num > 19) { num = num % 10; }
            if (num == 1) { word = words[0]; }
            else if (num == 2 || num == 3 || num == 4) { word = words[1]; }
            else { word = words[2]; }
            return str(initial_num) + " " + word
        }
    };

    /**
     * Wrapper for suit
     * @param templateName
     * @returns {{execute: Function, api: Function}}
     */
    this.template = function(templateName) {
        return {
            "execute": function(data, callback, listenersAction) {
                return suit.SuitApi.executeTemplate(templateName, data, callback, listenersAction);
            },
            "api": function() { return suit.SuitApi.getTemplateApi(templateName) }
        }
    };
};

/**
 * RunTime Helpers for Suit
 * @constructor
 */
var SuitRunTime = function() {

    this.stringify = function(variable) {
        var type = typeof(variable);
        if (type == "number" || type == "string") { return variable.toString(); }
        else if ( variable instanceof Array || variable instanceof Object) { return JSON.stringify(variable); }
        else if ( type == "boolean" ) { return variable; }
        else { return undefined; }
    };

    this.variable = function(lambdavar, default_or_null) {
        try {
            var res = lambdavar();
            if (res === null || res === undefined) { return default_or_null; }
            return res;
        } catch(e) { return default_or_null; }
    };


    this.opt = function(condition, trueblock, falseblock) {
        return eval(condition) ? trueblock() : falseblock();
    };


    this.list = function(itemGeneratorFunction, iterable) {
        var result = "";
        if (iterable instanceof Array) {
            for (var i = 0; i < iterable.length; i++) { result += itemGeneratorFunction(i); }
        } else {
            for (var key in iterable) { result += itemGeneratorFunction(key); }
        }
        return result;
    };

};

/**
 * RunTime Filters for Suit
 * @constructor
 */
var SuitFilters = function() {

    this.get_length = function(variable) {
        if (typeof(variable) == "object") {
            var counter = 0;
            for (k in variable) counter++;
            return counter;
        }
        return variable == null ? 0 : this.int2str(variable).length
    };

    this.plural_form = function(number, forms) {
        return suit.utils.pluralForm(number, forms);
    };

    this.startswith = function(stringVar, substring) {
        if (stringVar == null || substring == null) { return false }
        return (stringVar.indexOf(substring) == 0);
    };

    this.inArray = function(needle, haystack) {
        if (needle == null || haystack == null) { return false }
        if (typeof(haystack) == "string"){ return !!(haystack.indexOf(needle) > -1); }
        else if (haystack instanceof Array) {
            for (var i in haystack) { if (haystack[i] == needle)  { return true; } }
            return false;
        }
        else if (haystack instanceof Object) { return (needle in haystack); } else { return false; }
    };

    this.contains = function(haystack, needle) {
         return this.inArray(needle, haystack);
    };

    this.to_bool = function(obj) {
        if (obj == null) return false;
        var falses = { "false": true, "False": true, "null": true };
        return !falses[obj];
    };

    this.str2int = function(value) {
        return parseInt(value);
    };

    this.to_str = function(variable) {
        return '\\"' + variable + '\\"'
    };

    this.int2str = function(obj) {
        if (obj == null) return "";
        if (typeof(obj) == "number") {
            return obj.toString();
        }
        return obj;
    };

    this.dateformat = function(date, format_str) {
        date = new Date(date);
        var pad = function (val) {
            val = String(val);
            return val.length == 1 ? "0" + val : val;
        };
        format_str = format_str.replace("%d", pad(date.getDate()));
        format_str = format_str.replace("%m", pad(date.getMonth() + 1));
        format_str = format_str.replace("%y", String(date.getFullYear())[2] + String(date.getFullYear())[3]);
        format_str = format_str.replace("%Y", date.getFullYear());
        format_str = format_str.replace("%H", pad(date.getHours()));
        format_str = format_str.replace("%M", pad(date.getMinutes()));
        format_str = format_str.replace("%S", pad(date.getSeconds()));
        return format_str;
    };

    this.usebr = function(text) {
        return text.replace("\n", "<br />");
    }

};

/**
 * SuitApi
 * @constructor
 */
var SuitApi = function() {

    this.templates = {};
    this.api_container = {};

    this.addTemplate = function(templateName, templateRenderCallback, initApiCallback) {
        this.templates[templateName] = { render: templateRenderCallback, initApi: initApiCallback, "inited": false};
    };

    this.updateListeners = function() {
        $(".ui-container").each(function() {
            var templateName = $(this).attr("data-template-name");
            if (templateName) {
                var api = suit.template(templateName).api();
                if (api) api._createListeners();}
        });
    };

    this.executeTemplate = function(templateName, data, callback, listenersAction) {
        if (data == null) { data = {}; }
        var html = this.templates[templateName].render(data);
        if (this.templates[templateName] !== undefined) {
            var api = this.getTemplateApi(templateName);
            if (api && api._createListeners) {
                api._createListeners();
            }
            if (callback !== undefined) {
                callback(html, api);
                this.updateListeners();
                return null;
            } else {
                setTimeout(this.updateListeners, 200);
                return html;
            }
        } else { return ""; }
    };

    this.getTemplateApi = function(templateName) {
        if (this.api_container[templateName] !== undefined) {
            return this.api_container[templateName];
        } else {
            if (this.templates[templateName] !== undefined) {
                if (typeof(this.templates[templateName]["initApi"]) == "function") {
                    this.api_container[templateName] = this.templates[templateName].initApi();
                    return this.api_container[templateName];
                }
            }
        }
    };
};
suit = new Suit();
suit.SuitRunTime = new SuitRunTime();
suit.SuitFilters = new SuitFilters();
suit.SuitApi = new SuitApi();
suit.events_controller = new suit.EventsController();
suit.error_controller = new suit.ErrorController();

String.prototype.format = function() {
    var args = arguments;
    return this.replace(/{(\d+)}/g,
        function(match, number) {
            return typeof args[number] != 'undefined' && args[number] != null ? args[number] : "null";
        }
    );
};

/* UI-containers initialization */
if (typeof $ !== "undefined") {
    $(document).ready(function() {
        suit.SuitApi.updateListeners();
    });
}
