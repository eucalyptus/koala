/**
   * @fileOverview Common JS for Custom Filters
   * @requires AngularJS, jQuery, and Purl jQuery URL parser plugin
**/

angular.module('CustomFilters', [])
.filter('escapeURL', function() {
    return function(input) {
      return encodeURIComponent(input);
    };
})
.filter('escapeHTMLTagID', function() {
    return function(input) {
      return encodeURIComponent(input).replace(/[%~!'\.\*\(\)]/g, "_");
    };
})
.filter('ellipsis', function () {
    return function (line, num) {
        if( line === null || line.length === 0 ){
            return "";
        }else if( line.length <= num ){
            return line;
        }
        return line.substring(0, num) + "...";
    };
})
.filter('bytes', function() {
    return function(bytes, precision) {
        if (bytes === 0) return '';
        if (isNaN(parseFloat(bytes)) || !isFinite(bytes)) return '-';
        if (typeof precision === 'undefined') precision = 1;
        var units = ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB'],
            number = Math.floor(Math.log(bytes) / Math.log(1024));
        return (bytes / Math.pow(1024, Math.floor(number))).toFixed(precision) +  ' ' + units[number];
    };
})
.filter('titleCase', function () {
    return function (input) {
        input = input.replace('_', ' ').toLowerCase();
        return input.replace(/^(\w)/, function (substr) {
            return substr.toUpperCase();
        });
    };
})
.filter('urlSafe', function () {
    return function (input) {
        var gen_delims = /[:\/\?#\[\]@\s]+/g;
        var sub_delims = /[!\$&\'\(\)\*\+,;=]+/g;
        input = input.replace(gen_delims, '-');
        input = input.replace(sub_delims, '');
        return input.toLowerCase();
    };
})
.filter('toClassName', function () {
    return function (input) {
        return input.replace(/ /g, '_').toLowerCase();
    };
})
;
