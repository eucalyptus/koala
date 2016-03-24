/**
 * @fileOverview Volume page JS
 * @requires AngularJS
 *
 */

angular.module('VolumePage', ['TagEditor', 'EucaConsoleUtils'])
    .controller('VolumePageCtrl', function ($scope, $http, $timeout, eucaUnescapeJson, eucaHandleError) {
        $http.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';
        $scope.volumeStatusEndpoint = '';
        $scope.transitionalStates = ['creating', 'deleting', 'attaching', 'detaching'];
        $scope.volumeStatus = '';
        $scope.volumeAttachStatus = '';
        $scope.snapshotId = '';
        $scope.instanceId = '';
        $scope.isNotValid = true;
        $scope.isNotChanged = true;
        $scope.isSubmitted = false;
        $scope.isUpdating = false;
        $scope.fromSnapshot = false;
        $scope.volumeSize = 1;
        $scope.snapshotSize = 1;
        $scope.urlParams = $.url().param();
        $scope.pendingModalID = '';
        $scope.initController = function (optionsJson) {
            var options = JSON.parse(eucaUnescapeJson(optionsJson));
            $scope.initChosenSelectors();
            $scope.initAvailZoneChoice();
            $scope.volumeStatusEndpoint = options.volume_status_json_url;
            $scope.volumeStatus = options.volume_status ? options.volume_status.replace('-', ' ') : '';
            $scope.volumeAttachStatus = options.attach_status;
            if ($scope.volumeStatusEndpoint) {
                $scope.getVolumeState();
            }
            $scope.setWatch();
            $scope.setFocus();
        };
        $scope.isTransitional = function (state) {
            return $scope.transitionalStates.indexOf(state) !== -1;
        };
        $scope.populateVolumeSize = function () {
           if ($scope.snapshotId === '') {
                $scope.snapshotSize = 1;
                $scope.volumeSize = 1;
                return;
            }
            $http.get("/snapshots/"+$scope.snapshotId+"/size/json").success(function(oData) {
                var results = oData ? oData.results : '';
                if (results) {
                    $scope.snapshotSize = results;
                    $scope.volumeSize = results;
                }
            }).error(function (oData, status) {
                eucaHandleError(oData, status);
            });
        };
        $scope.initChosenSelectors = function () {
            var snapshotField = $('#snapshot_id');
            if ($scope.urlParams.from_snapshot) {  // Pre-populate snapshot if passed in query string arg
                $scope.fromSnapshot = true;
                snapshotField.val($scope.urlParams.from_snapshot);
                $scope.snapshotId = $scope.urlParams.from_snapshot;
                $scope.populateVolumeSize();
            }
            snapshotField.chosen({'width': '50%', 'search_contains': true});
            // Instance choices in "Attach to instance" modal dialog
            $('#attach-volume-modal').on('open.fndtn.reveal', function() {
                $('#instance_id').chosen({'width': '75%', search_contains: true});
            });
            // Open attach modal based on URL params
            if ($scope.urlParams.attachmodal) {
                $timeout(function() {
                    $scope.openModalById('attach-volume-modal');
                }, 300 );
            }
        };
        $scope.initAvailZoneChoice = function () {
            var availZoneParam = $scope.urlParams.avail_zone;
            if (availZoneParam) {
                $('#zone').val(availZoneParam);
            }
        };
        $scope.getVolumeState = function () {
            $http.get($scope.volumeStatusEndpoint).success(function(oData) {
                var results = oData ? oData.results : '';
                if (results) {
                    $scope.volumeStatus = results.volume_status;
                    $scope.volumeAttachStatus = results.attach_status;
                    $scope.device_name = results.attach_device;
                    $scope.attach_time = results.attach_time;
                    $scope.attach_instance = results.attach_instance;
                    // Poll to obtain desired end state if current state is transitional
                    if ($scope.isTransitional($scope.volumeStatus) || $scope.isTransitional($scope.volumeAttachStatus)) {
                        $scope.isUpdating = true;
                        $timeout(function() {$scope.getVolumeState();}, 4000);  // Poll every 4 seconds
                    } else {
                        $scope.isUpdating = false;
                    }
                }
            });
        };
        $scope.getDeviceSuggestion = function () {
            // TODO: the url shouldn't be built by hand, pass value from request.route_path!
            $http.get("/instances/"+$scope.instanceId+"/nextdevice/json").success(function(oData) {
                var results = oData ? oData.results : '';
                if (results) {
                    $('input#device').val(results);
                }
            });
        };
        // True if there exists an unsaved key or value in the tag editor field
        $scope.existsUnsavedTag = function () {
            var hasUnsavedTag = false;
            $('input.taginput[type!="checkbox"]').each(function(){
                if ($(this).val() !== '') {
                    hasUnsavedTag = true;
                }
            });
            return hasUnsavedTag;
        };
        $scope.openModalById = function (modalID) {
            var modal = $('#' + modalID);
            modal.foundation('reveal', 'open');
            modal.find('h3').click();  // Workaround for dropdown menu not closing
            // Clear the pending modal ID if opened
            if ($scope.pendingModalID === modalID) {
                $scope.pendingModalID = '';
            }
        };
        $scope.setWatch = function () {
            // Monitor the action menu click
            $(document).on('click', 'a[id$="action"]', function (event) {
                // Ingore the action if the link has a ng-click attribute
                if (this.getAttribute('ng-click')) {
                    return;
                }
                // the ID of the action link needs to match the modal name
                var modalID = this.getAttribute('id').replace("-action", "-modal");
                // If there exists unsaved changes, open the wanring modal instead
                if ($scope.existsUnsavedTag() || $scope.isNotChanged === false) {
                    $scope.pendingModalID = modalID;
                    $scope.openModalById('unsaved-changes-warning-modal');
                    return;
                } 
                $scope.openModalById(modalID);
            });
            // Leave button is clicked on the warning unsaved changes modal
            $(document).on('click', '#unsaved-changes-warning-modal-stay-button', function () {
                $('#unsaved-changes-warning-modal').foundation('reveal', 'close');
            });
            // Stay button is clicked on the warning unsaved changes modal
            $(document).on('click', '#unsaved-changes-warning-modal-leave-link', function () {
                $scope.openModalById($scope.pendingModalID);
            });
            $scope.$on('tagUpdate', function($event) {
                $scope.isNotChanged = false;
            });
            $scope.$watch('volumeSize', function () {
                if ($scope.volumeSize < $scope.snapshotSize || $scope.volumeSize === undefined) {
                    $('#volume_size_error').removeClass('hide');
                    $scope.isNotValid = true;
                }else{
                    $('#volume_size_error').addClass('hide');
                    $scope.isNotValid = false;
                }
            });
            // Handle the unsaved tag issue
            $(document).on('submit', '#volume-detail-form', function(event) {
                $('input.taginput').each(function(){
                    if ($(this).val() !== '') {
                        event.preventDefault(); 
                        $scope.isSubmitted = false;
                        $('#unsaved-tag-warn-modal').foundation('reveal', 'open');
                        return false;
                    }
                });
            });
            // Turn "isSubmiited" flag to true when a submit button is clicked on the page
            $('form[id!="euca-logout-form"]').on('submit', function () {
                $scope.isSubmitted = true;
            });
            // Conditions to check before navigate away
            window.onbeforeunload = function(event) {
                if ($scope.isSubmitted === true) {
                   // The action is "submit". OK to proceed
                   return;
                }else if ($scope.existsUnsavedTag() || $scope.isNotChanged === false) {
                    // Warn the user about the unsaved changes
                    return $('#warning-message-unsaved-changes').text();
                }
                return;
            };
            // Do not perfom the unsaved changes check if the cancel link is clicked
            $(document).on('click', '.cancel-link', function(event) {
                window.onbeforeunload = null;
            });
            $(document).on('submit', '[data-reveal] form', function () {
                $(this).find('.dialog-submit-button').css('display', 'none');                
                $(this).find('.dialog-progress-display').css('display', 'block');                
            });
            $(document).on('input', 'input[type="text"]', function () {
                $scope.isNotChanged = false;
                $scope.$apply();
            });
        };
        $scope.setFocus = function () {
            $(document).on('ready', function(){
                var tabs = $('.tabs').find('a');
                if (tabs.length > 0) {
                    tabs.get(0).focus();
                } else if ($('input[type="text"]').length > 0) {
                    $('input[type="text"]').get(0).focus();
                }
            });
            $(document).on('opened.fndtn.reveal', '[data-reveal]', function () {
                var modal = $(this);
                var modalID = $(this).attr('id');
                if (modalID.match(/terminate/) || modalID.match(/delete/) || modalID.match(/release/)) {
                    var closeMark = modal.find('.close-reveal-modal');
                    if (!!closeMark) {
                        closeMark.focus();
                    }
                }else{
                    var inputElement = modal.find('input[type!=hidden]').get(0);
                    var modalButton = modal.find('button').get(0);
                    if (!!inputElement) {
                        inputElement.focus();
                    } else if (!!modalButton) {
                        modalButton.focus();
                    }
               }
            });
        };
        $scope.detachModal = function (isRootVolume) {
            var warnModalID = 'detach-volume-warn-modal',
                detachModalID = 'detach-volume-modal';
            if (isRootVolume === 'True') {
                $scope.pendingModalID = warnModalID;
            } else {
                $scope.pendingModalID = detachModalID;
            }
            if ($scope.existsUnsavedTag() || $scope.isNotChanged === false) {
                $scope.openModalById('unsaved-changes-warning-modal');
                return;
            }
            $scope.openModalById($scope.pendingModalID);
        };
    })
;

