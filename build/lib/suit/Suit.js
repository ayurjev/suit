
var Suit = function() {
    var events_listeners = {};

    this.universal_id = function (that) {
        if (that.id) return that.id;

        if (that.jquery) {
            if (that.attr("data-template-name")) {
                return that.attr("data-template-name")
            }

            if (that.selector) {
                return that.selector
            }
        }
        return that;
    };

    this.on = function(initiator, event_name, selector, cb) {
        var initiator_id = this.universal_id(initiator);
        var selector_id = this.universal_id(selector);
        var event_id = "[" + selector_id + "]" + event_name;

        if (!events_listeners[initiator_id]) {
            events_listeners[initiator_id] = {};
        }
        if (!events_listeners[initiator_id][event_id]) {
            events_listeners[initiator_id][event_id] = [];
        }
        for (var i = 0; i < events_listeners[initiator_id][event_id].length; i++) {
            if (events_listeners[initiator_id][event_id][i].toString() == cb.toString()) {
                if (initiator.attr) {
                    if (initiator.attr("ui-container-loaded")) return;
                } else {
                    return;
                }
            }
        }

        events_listeners[initiator_id][event_id].push(cb);
        initiator.on(event_name, selector, cb);
    };

    this.connect = function(p1, p2, p3, p4) {

        if (p1 instanceof Array) {
            $.each(p1, function(num, subp1) {
                suit.connect(subp1, p2, p3, p4);
            });
        } else {
            var initiator_selector = p1;
            var event_name = p2;
            if (p4 == undefined) {
                this.on($("body"), event_name, initiator_selector, p3);
            }
            else {
                if (initiator_selector.on) {
                    this.on(initiator_selector, event_name, p3, p4);
                } else {
                    throw new Error("there is no method 'on' in object '" + initiator_selector + "'");
                }
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

    this.websocket = function (url, error_suppression) {
        var ec = new this.EventsController();
        ec.ws = new WebSocket(url);
        ec.ws.onmessage = function (event) {
            var data = JSON.parse(event.data);
            if (!error_suppression || error_suppression(data) !== true)
                suit.events_controller.broadcast("XHR_Request_Completed", data, error_suppression);
            ec.broadcast("onmessage", data);
            if (data.ws && data.ws.event) {
                ec.broadcast(data.ws.event, data);
            }
        };
        ec.ws.onopen = function (event) { ec.broadcast("onopen", event) };
        ec.ws.onclose = function (event) { ec.broadcast("onclose", event) };
        ec.send = function(action, data) {
            data = data || {};
            data.action = action;
            ec.ws.send(JSON.stringify(data));
        };
        return ec;
    };

    /**
     * Upload with usage of FormData
     * @param url
     * @param data
     * @param cb
     * @param error_suppression
     * @returns {{}}
     */
    this.ajax_upload = function (url, data, cb, error_suppression) {
        var responseData = {};
        var form_data = new FormData();
        $.each(data, function (key, value) {
            form_data.append(key, value);
        });

        $.ajax({
            url:        url,
            async:      !!cb,
            type:       "POST",
            dataType:   "json",
            data:       form_data,
            contentType: false,
            processData: false
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
            $(container).bind("success.pjax", function (event, data) {
                suit.events_controller.broadcast("XHR_Request_Completed", data);
                return cb(data)
            });
            $(container).bind("error.pjax", function (jqXHR, textStatus, errorThrown) {
                suit.events_controller.broadcast("UnknownError", jqXHR, textStatus, errorThrown);
            });
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
        internal.on = function(eventName, subscriber, cb) {
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
            return initial_num + " " + suit.utils.pluralWord(initial_num, words)
        },
        "pluralWord": function(initial_num, words) {
            words = JSON.parse(words);
            var num = parseInt(initial_num) % 100;
            var word;
            if (num > 19) { num = num % 10; }
            if (num == 1) { word = words[0]; }
            else if (num == 2 || num == 3 || num == 4) { word = words[1]; }
            else { word = words[2]; }
            return word
        },
        fnDelay: (function(){
            var timer = 0;
            return function(callback, ms){
                clearTimeout(timer);
                timer = setTimeout(callback, ms);
            };
        })()
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
    this.entityMap = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': '&quot;',
        "'": '&#39;',
        "/": '&#x2F;'
    };
    this.escapeHtml = function(string) {
        var entityMap = this.entityMap;
        return String(string).replace(/[&<>"'\/]/g, function (s) {
            return entityMap[s];
        });
    };

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
            /* Проверка на null, undefined, NaN */
            if (res === null || res === undefined || res !== res) { return default_or_null; }
            return typeof(res) == "string" ? this.escapeHtml(res) : res;
        } catch(e) { return default_or_null; }
    };

    this.include = function(iter_dict, template_name, data_func, template_part_to_become_scope_data) {
        var main_data = data_func();
        var new_data = main_data;

        for (var iter_key in iter_dict) {
            new_data[iter_key] = iter_dict[iter_key];
        }

        var scope_data = JSON.parse(template_part_to_become_scope_data(main_data));
        for (var key in scope_data) {
            new_data[key] = scope_data[key];
        }
        return suit.template(template_name).execute(new_data);
    };

    this.opt = function(condition, trueblock, falseblock) {
        if (condition.indexOf("\\") > -1)
            return eval('"'+condition+ '"') ? trueblock() : falseblock();
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

    this.intersection = function(A,B)
    {
        var M=A.length, N=B.length, C=[];
        for (var i=0; i<M; i++)
        { var j=0, k=0;
            while (B[j]!==A[i] && j<N) j++;
            while (C[k]!==A[i] && k<C.length) k++;
            if (j!=N && k==C.length) C[C.length]=A[i];
        }
        return C;
    };

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

    this.plural_word = function(number, forms) {
        return suit.utils.pluralForm(number, forms);
    };

    this.startswith = function(stringVar, substring) {
        if (stringVar == null || substring == null) { return false }
        return (stringVar.indexOf(substring) == 0);
    };

    this.inArray = function(needle, haystack) {
        if (typeof(haystack) == "string") {
            try {
                haystack = JSON.parse(haystack);
            } catch (e) {}
        }
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
        return '"' + variable + '"'
    };

    this.html = function(variable) {
        variable = String(variable).replace(/&amp;/g, "&");
        variable = String(variable).replace(/&lt;/g, "<");
        variable = String(variable).replace(/&gt;/g, ">");
        variable = String(variable).replace(/&quot;/g, '"');
        variable = String(variable).replace(/&#39;/g, "'");
        variable = String(variable).replace(/&#x2F;/g, "/");
        return decodeURI(variable);
    };

    this.int2str = function(obj) {
        if (obj == null) return "";
        if (typeof(obj) == "number") {
            return obj.toString();
        }
        return obj;
    };

    this.dateformat = function(date, format_str) {
        var date_obj = new Date(date);
        if (Object.prototype.toString.call(date_obj) != "[object Date]" || isNaN(date_obj.getTime())) {
            return date;
        }
        var pad = function (val) {
            val = String(val);
            return val.length == 1 ? "0" + val : val;
        };
        format_str = format_str.replace("%d", pad(date_obj.getDate()));
        format_str = format_str.replace("%m", pad(date_obj.getMonth() + 1));
        format_str = format_str.replace("%y", String(date_obj.getFullYear())[2] + String(date_obj.getFullYear())[3]);
        format_str = format_str.replace("%Y", date_obj.getFullYear());
        format_str = format_str.replace("%H", pad(date_obj.getHours()));
        format_str = format_str.replace("%M", pad(date_obj.getMinutes()));
        format_str = format_str.replace("%S", pad(date_obj.getSeconds()));
        return format_str;
    };

    this.usebr = function(text) {
        return text.replace("\n", "<br />");
    };

    this.values = function(haystask) {
        return Object.keys(haystask).map(function(key){return haystask[key]})
    };

};

/**
 * SuitApi
 * @constructor
 */
var SuitApi = function() {
    this.templates = {};
    var unique_api_id = 1;

    this.makeTemplateApi = function(cb) {
        return function () {
            var internal = {};
            var id = unique_api_id++;
            internal.ui = {};
            internal.ui.body = $("body");
            internal.error_controller = new suit.ErrorController();
            internal.events_controller = new suit.EventsController();
            internal.error_controller.id = "error_controller." + id;
            internal.events_controller.id = "events_controller." + id;
            internal.data = suit.environment;
            internal.api = {};

            if (cb) cb(internal);

            internal.api.id = "api." + id;
            internal.api._createListeners = function() { if (internal.api.createListeners) internal.api.createListeners(); };
            internal.api._register_self = function(self) { internal.self = self; $.data(internal.self[0], "api", internal.api); };
            internal.refresh = function(data, target_data_container_name) {
                var html = suit.template(internal.self.attr("data-template-name")).execute(data);
                var new_ui_container = $('[data-template-name="'+internal.self.attr("data-template-name")+'"]', $("<div>" + html + "</div>"));

                /* Сперва ищем все контейнеры внутри шаблона (включая вложенные) */
                var inner_containers = $(".data-container", internal.self);
                var new_inner_containers = $(".data-container", new_ui_container);
                if (inner_containers.length != new_inner_containers.length && !target_data_container_name) {
                    /* Если получили ошибку - пробуем использовать замену только для шаблонов самого верхнего уровня */
                    inner_containers = $(internal.self).children(".data-container");
                    new_inner_containers = $(new_ui_container).children(".data-container");
                    if (inner_containers.length != new_inner_containers.length && !target_data_container_name) {
                        throw new Error("Ошибка композиции шаблонов: при выполнении метода refresh() кол-во data-container'ов не совпадает");
                    }
                }

                if (inner_containers.length == 0) {
                    internal.self.html($(html).html());
                    $(".ui-container", internal.self).attr("ui-container-loaded", null);
                } else {
                    /* Ищем все ui-container'ы внутри каждого data_container'a обновляемого шаблона и сохраним их api */
                    /* Это обязательно надо сделать в отдельном цикле each, чтобы избежать ерунды с ненужным замыканием */
                    var childs_ui_containers_api = {};
                    inner_containers.each(function(num, inner_container) {
                        $(".ui-container", $(inner_container)).each(function (uc_num, child_ui_container) {
                            childs_ui_containers_api[num.toString() + "_" + uc_num.toString()] = $(child_ui_container).data("api");
                        });
                    });

                    /* И в отдельном цикле мы меняем содержимое html-блоков, а потом ставим  им сохраненные ранее api */
                    $(".data-container", internal.self).each(function(num, inner_container) {
                        if (target_data_container_name) {
                            if ($(inner_container).attr("data-part-name") == target_data_container_name) {
                                for (var i=0; i<new_inner_containers.length;i++) {
                                    if ($(new_inner_containers[i]).attr("data-part-name") == target_data_container_name) {
                                        $(inner_container).html($(new_inner_containers[i]).html());
                                    }
                                }
                            }
                        } else {
                            $(inner_container).html($(new_inner_containers[num]).html() || "");
                        }

                        /* Возвращаем экземпляры api обратно в их ui-container'ы */
                        $(".ui-container", $(inner_container)).each(function (uc_num, child_ui_container) {
                            if (childs_ui_containers_api[$(child_ui_container).attr("data-template-name")]) {
                                $(child_ui_container).data("api", childs_ui_containers_api[num.toString() + "_" + uc_num.toString()]);
                            }
                        });
                    });
                }
                suit.updateListeners();
                internal.api._createListeners();
            };
            internal.connect = function(selector, event, cb) {
                if (selector instanceof Array) {
                    selector.each(function(num, subselector) {
                        suit.connect(internal.self, event, subselector, cb);
                    })
                } else {
                    suit.connect(internal.self, event, selector, cb);
                }
            };
            internal.widget = function(data_template_name, host_container) {
                var hc = host_container ? host_container : internal.self;
                if (!(host_container instanceof $)) {
                    hc =  host_container ? $(host_container, internal.self) : internal.self;
                }
                var widget = hc.find("[data-template-name='"+data_template_name+"']:first");
                return widget.data("api");
            };
            internal.widgets = function(data_template_name, host_container) {
                var hc = host_container ? host_container : internal.self;
                if (!(host_container instanceof $)) {
                    hc =  host_container ? $(host_container, internal.self) : internal.self;
                }
                var widgets = hc.find("[data-template-name='"+data_template_name+"']");
                var widgets_api = [];
                $.each(widgets, function(num, widget) {
                    widgets_api.push($(widget).data("api"));
                });
                return widgets_api;
            };
            if (!internal.api.refresh) internal.api.refresh = internal.refresh;
            return internal.api;
        }
    };

    this.addTemplate = function(templateName, templateRenderCallback, initApiCallback) {
        this.templates[templateName] = { render: templateRenderCallback, initApi: this.makeTemplateApi(initApiCallback)};
    };

    this.executeTemplate = function(templateName, data) {
        return this.templates[templateName].render(data || {});
    };

    this.getTemplateApi = function(templateName) {
        return $("body").find("[data-template-name='"+templateName+"']:first").data("api") || this.templates[templateName].initApi();
    };
};

suit = new Suit();
suit.SuitRunTime = new SuitRunTime();
suit.SuitFilters = new SuitFilters();
suit.SuitApi = new SuitApi();
suit.events_controller = new suit.EventsController();
suit.error_controller = new suit.ErrorController();
suit.events_controller.id = "suit.EventsController";
suit.error_controller.id = "suit.ErrorController";

suit.load = function() {
    if ($(this).find(".ui-container").length) {
        $(this).find(".ui-container").each(suit.load);
    }
    if (!$(this).attr("ui-container-loaded")) {
        var templateName = $(this).attr("data-template-name");
        if (templateName) {
            try {
                var api = $(this).data("api") || suit.SuitApi.templates[templateName].initApi();
            } catch (e) {
                console.log("there is no template with name '" + templateName + "'");
            }
            if (api) api._register_self($(this));
            if (api) api._createListeners();
            $(this).attr("ui-container-loaded", true)
        }
    }
};

suit.updateListeners = function() {
    $(".ui-container").each(suit.load);
};


String.prototype.format = function() {
    var args = arguments;
    return this.replace(/{(\d+)}/g,
        function(match, number) {
            return typeof args[number] != 'undefined' && args[number] != null ? args[number] : "null";
        }
    );
};

$.fn.putBefore = function(dest){
    return this.each(function(){
        $(dest).before($(this));
    });
};
$.fn.putAfter = function(dest){
    return this.each(function(){
        $(dest).after($(this));
    });
};

/* UI-containers initialization */
if (typeof $ !== "undefined") {

    $(document).ready(function() {

        if (window.suit_environment) {
            try {
                suit.environment = JSON.parse(window.suit_environment);
                $("#suit_environment_script").remove();
            } catch (e) { console.log("suit environment loading failed: " + e.toString()); return; }
            if (suit.environment) {
                suit.events_controller.on("XHR_Request_Completed", suit, function(data) {
                    var changes = [];
                    if (data.result) {
                        for(var key in data.result) {
                            if (key in suit.environment && suit.environment[key] != data.result[key]) {
                                suit.environment[key] = data.result[key];
                                changes.push(key);
                            }
                        }
                        if (changes.length) {
                            $('[auto-refresh]').each(function(num, arblock) {
                                var variables = $(arblock).attr("auto-refresh").split(",");
                                if (suit.SuitFilters.intersection(variables, changes).length) {
                                    if ($(arblock).hasClass("ui-container")) {
                                        $(arblock).data("api").refresh(suit.environment);
                                    } else if ($(arblock).hasClass("data-container") && $(arblock).attr("data-part-name").length) {
                                        $(arblock).parent(".ui-container").data("api").refresh(suit.environment, $(arblock).attr("data-part-name"));
                                    }
                                }
                            });
                        }
                    }
                });
            }
        }

        suit.updateListeners();
    });
}
