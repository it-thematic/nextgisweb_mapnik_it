define([
    "dojo/_base/declare",
    "dojo/_base/lang",
    "dojo/Deferred",
    "dojo/when",
    "dijit/_TemplatedMixin",
    "dijit/_WidgetsInTemplateMixin",
    "dijit/layout/ContentPane",
    "ngw-pyramid/i18n!mapnik",
    "ngw-pyramid/hbs-i18n",
    "ngw-resource/serialize",
    // resource
    "dojo/text!./template/MapnikStyleWidget.hbs",
    // template
    "dojox/layout/TableContainer",
    "ngw-file-upload/Uploader"
], function (
    declare,
    lang,
    Deferred,
    when,
    _TemplatedMixin,
    _WidgetsInTemplateMixin,
    ContentPane,
    i18n,
    hbsI18n,
    serialize,
    template
) {
    return declare([ContentPane, serialize.Mixin, _TemplatedMixin, _WidgetsInTemplateMixin], {
        templateString: hbsI18n(template, i18n),
        title: i18n.gettext("Mapnik style"),
        prefix: "mapnik_vector_style",

        serializeInMixin: function (data) {
            var prefix = this.prefix,
                setObject = function (key, value) { lang.setObject(prefix + "." + key, value, data); };

            setObject("file_upload", this.wFileUpload.get("value"));
        },

        validateDataInMixin: function (errback) {
            return this.composite.operation == "create" ?
                this.wFileUpload.upload_promise !== undefined &&
                    this.wFileUpload.upload_promise.isResolved() : true;
        }

    });
});
