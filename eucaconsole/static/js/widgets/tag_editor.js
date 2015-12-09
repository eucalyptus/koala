/**
 * @fileOverview Tag Editor JS
 * @requires AngularJS
 *
 */
angular.module('TagEditor', ['ngSanitize', 'EucaConsoleUtils', 'FormComponents'])
    .filter('ellipsis', function () {
        return function (line, num) {
            if (!line) return line;
            if (line.length <= num) {
                return line;
            }
            return line.substring(0, num) + "...";
        };
    })
    .controller('TagEditorCtrl', function ($scope, $sanitize, $timeout, eucaUnescapeJson) {
        $scope.tagEditor = undefined;
        $scope.tagInputs = undefined;
        $scope.tagsTextarea = undefined;
        $scope.tagsArray = [];
        $scope.newTagKey = '';
        $scope.newTagValue = '';
        $scope.tagKeyClass = '';
        $scope.showNameTag = true;
        $scope.existsTagKey = false;
        $scope.isTagNotComplete = true;
        $scope.visibleTagsCount = 0;
        $scope.tagCount = 0;
        $scope.syncTags = function () {
            var tagsObj = {};
            $scope.tagsArray.forEach(function(tag) {
                tagsObj[tag.name] = tag.value;
            });
            $scope.tagsTextarea.val(JSON.stringify(tagsObj));
            // Update visible tags count, ignoring "Name" tag when present.
            $scope.updateVisibleTagsCount();
        };
        $scope.updateVisibleTagsCount = function () {
            if ($scope.showNameTag) {
                $scope.visibleTagsCount = $scope.tagsArray.length;
            } else {
                // Adjust count if "Name" tag is in tagsArray
                $scope.visibleTagsCount = $.map($scope.tagsArray, function (item) {
                    if (item.name !== 'Name') { return item; }
                }).length;
            }
        };
        $scope.updateTagCount = function () {
            $scope.tagCount = $scope.tagsArray.length;
            // Add +1 to the tag count if a name is entered on the form 
            if ($scope.isNameTagIncluded() === false) { 
                if ($('#security-group-detail-form').length > 0) {
                    // security groups have their own name attributes, thus skip
                    return;
                } else if ($('#launch-instance-form').length > 0) {
                    // Sepcial case: instance launch wizard page can have mutiple name fields
                    var isNameEntered = false;
                    $('input.name').each(function() {
                        if ($(this).val().length > 0) {
                            isNameEntered = true;
                        } 
                    }); 
                    if (isNameEntered) {
                        $scope.tagCount += 1;
                    }
                } else {
                    // check if the name field has a value entered
                    if ($('#name').length && $('#name').val().length > 0) {
                        $scope.tagCount += 1;
                    }
                }
            }
        };
        $scope.isNameTagIncluded = function () {
            var isIncluded = false;
            angular.forEach($scope.tagsArray, function(x) {
                if (x.name == 'Name') {
                    isIncluded = true;
                }
            });
            return isIncluded;
        };
        $scope.initTags = function(optionsJson) {
            var options = JSON.parse(eucaUnescapeJson(optionsJson));
            var tagsObj = options.tags;
            Object.keys(tagsObj).forEach(function(key) {
                if (!key.match(/^aws:.*/) && !key.match(/^euca:.*/)) {
                    $scope.tagsArray.push({
                        'name': key,
                        'value': tagsObj[key]
                    });
                }
            });
            $scope.tagEditor = $('#tag-editor');
            $scope.tagInputs = $scope.tagEditor.find('.taginput');
            $scope.tagsTextarea = $scope.tagEditor.find('textarea#tags');
            $('#tag-name-input').keydown(function(evt) {
                if (evt.keyCode === 13) {
                    evt.preventDefault();
                }
            });
            $('#tag-value-input').keydown(function(evt) {
                if (evt.keyCode === 13) {
                    evt.preventDefault();
                }
            });
            $scope.showNameTag = options.show_name_tag;
            $scope.syncTags();
            $scope.setWatch();
        };
        $scope.keyListener = function ($event) {
            if ($event.keyCode == 13) {
                $scope.addTag($event);
            }
        };
        $scope.getSafeTitle = function (tag) {
            return $sanitize(tag.name + ' = ' + tag.value);
        };
        $scope.removeTag = function (index, $event) {
            $event.preventDefault();
            $scope.tagsArray.splice(index, 1);
            $scope.syncTags();
            $scope.$emit('tagUpdate');
        };
        $scope.addTag = function ($event) {
            $event.preventDefault();
            $scope.checkRequiredInput();
            if ($scope.isTagNotComplete) {
                return;
            }
            var tagEntry = $($event.currentTarget).closest('.tagentry'),
                tagKeyField = tagEntry.find('.key'),
                tagValueField = tagEntry.find('.value'),
                tagsArrayLength = $scope.tagsArray.length,
                existingTagFound = false,
                form = $($event.currentTarget).closest('form');
            if (tagKeyField.val() && tagValueField.val()) {
                // disallow adding tags starting with aws: or euca:. abide handles
                // alerting the user
                if (tagKeyField.val().indexOf("aws:") === 0 ||
                    tagKeyField.val().indexOf("euca:") === 0) {
                    return false;
                }
                // Avoid adding a new tag if the name duplicates an existing one.
                for (var i=0; i < tagsArrayLength; i++) {
                    if ($scope.tagsArray[i].name === tagKeyField.val()) {
                        existingTagFound = true;
                        break;
                    }
                }
                if (existingTagFound) {
                    tagKeyField.focus();
                } else {
                    $scope.tagsArray.push({
                        'name': tagKeyField.val(),
                        'value': tagValueField.val(),
                        'fresh': 'new'
                    });
                    $scope.syncTags();
                    tagKeyField.val('').focus();
                    tagValueField.val('');
                    $scope.$emit('tagUpdate');
                    $scope.newTagKey = '';
                    $scope.newTagValue = '';
                }
            } else {
                if (tagKeyField.val()) {
                    tagValueField.focus();
                } else {
                    tagKeyField.focus();
                }
            }
        };
        $scope.checkRequiredInput = function () {
            if ($scope.checkDuplicatedTagKey()) {
                $scope.isTagNotComplete = true;
            } else if ($scope.newTagKey === '' || $scope.newTagValue === '') {
                $scope.isTagNotComplete = true;
            } else if ($('#tag-name-input-div').hasClass('error') ||
                $('#tag-value-input-div').hasClass('error')) {
                $scope.isTagNotComplete = true;
            } else if ($scope.tagEditorForm.$invalid) {
                $scope.isTagNotComplete = true;
            } else {
                $scope.isTagNotComplete = false;
            } 
        }; 
        // Check for the duplicated key and set the tagKeyClass to be 'error' if detected
        $scope.checkDuplicatedTagKey = function () {
            $scope.tagKeyClass = '';
            $scope.existsTagKey = false;
            angular.forEach($scope.tagsArray, function(tag) {
                if (tag.name == $scope.newTagKey) {
                    $scope.existsTagKey = true;
                    $scope.tagKeyClass = 'error';
                }
            }); 
            return $scope.existsTagKey;
        };
        $scope.setWatch = function () {
            $scope.$watch('newTagKey', function () {
                $scope.checkRequiredInput();
                // timeout is needed to react to Foundation's validation check
                $timeout(function() {
                    // repeat the check on input condition 
                    $scope.checkRequiredInput();
                }, 1000);
            });
            $scope.$watch('newTagValue', function () {
                $scope.checkRequiredInput();
                // timeout is needed to react to Foundation's validation check
                $timeout(function() {
                    // repeat the check on input condition 
                    $scope.checkRequiredInput();
                }, 1000);
            });
            $scope.setTagCountWatch();
        };
        $scope.setTagCountWatch = function () {
            // When the tagsArray get updated, check the tag count
            $scope.$watch('tagsArray', function () {
                $scope.updateTagCount();
                $scope.updateVisibleTagsCount();
            }, true);
            // When user enters name field, check the tag count
            if ($('#launch-instance-form').length !== 0) {
                // Special case for the launch instance wizard where mutiple name fields exist
                $(document).on('keyup', 'input.name', function (event) {
                    $scope.updateTagCount();
                    $scope.updateVisibleTagsCount();
                });
            } else {
                $(document).on('keyup', '#name', function (event) {
                    $scope.updateTagCount();
                    $scope.updateVisibleTagsCount();
                });
            }
        };
    })
;
