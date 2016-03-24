/**
 * @fileOverview Scaling Group detail page JS
 * @requires AngularJS
 *
 */

// Scaling Group page includes the AutoScale tag editor, so pull in that module as well.
angular.module('ScalingGroupPage', ['TagEditorModule', 'EucaConsoleUtils'])
    .directive('chosen', function () {
        return {
            scope: {
                model: '=ngModel'
            },
            restrict: 'A',
            require: 'ngModel',
            link: function (scope, element, attrs, ctrl) {
                var chosenAttrs = JSON.parse(attrs.chosen || '{}');
                for(var key in attrs) {
                    if(/^chosen-.*/.test(key)) {
                        chosenAttrs[key] = attrs[key];
                    }
                }
                element.chosen(chosenAttrs);

                element.on('change', function () {
                    scope.validateField(this);
                });
            },
            controller: ['$scope', '$element', function ($scope, $element) {
                $scope.validateField = function (element) {
                    var isValid = element[0].selectedIndex > -1,
                        form = this.form && this.form.name,
                        field = this.name;

                    if(form && field) {
                        $scope[form][field].$setValidity('required', isValid);
                    }
                };

                $scope.$watch('model', function () {
                    $scope.validateField($element);
                });
            }]
        };
    })
    .controller('ScalingGroupPageCtrl', function ($scope, $timeout, eucaUnescapeJson, eucaNumbersOnly) {
        $scope.minSize = 1;
        $scope.desiredCapacity = 1;
        $scope.maxSize = 1;
        $scope.terminationPoliciesUpdate = [];
        $scope.terminationPoliciesOrder = [];
        $scope.vpcSubnets = [];
        $scope.vpcSubnetZonesMap = {};
        $scope.isNotValid = false;
        $scope.isNotChanged = true;
        $scope.isSubmitted = false;
        $scope.pendingModalID = '';

        $scope.isInvalid = function () {
            return $scope.scalingGroupDetailForm.$invalid;
        };

        $scope.initChosenSelectors = function () {
            $('#launch_config').chosen({'width': '80%', search_contains: true});
            // Remove the option if it has no vpc subnet ID associated
            var selectVPCSubnetObject = $('#vpc_subnet option');
            if (selectVPCSubnetObject.length > 0) {
                if (selectVPCSubnetObject.first().attr('value') === '' ||
                    selectVPCSubnetObject.first().attr('value') == 'None') {
                    selectVPCSubnetObject.first().remove();
                } 
            }
            $('#vpc_subnet').chosen({'width': '80%', search_contains: true});
        };
        $scope.setInitialValues = function () {
            $scope.minSize = parseInt($('#min_size').val(), 10);
            $scope.desiredCapacity = parseInt($('#desired_capacity').val(), 10);
            $scope.maxSize = parseInt($('#max_size').val(), 10);
            // the order of the termination policy select options need to be arranged
            // before the chosen widget is initialized
            $scope.rearrangeTerminationPoliciesOptions($scope.terminationPoliciesOrder);
            $scope.createVPCSubnetZonesMap();
            $scope.setInitialVPCSubnets();
        };
        $scope.initController = function (optionsJson) {
            var options = JSON.parse(eucaUnescapeJson(optionsJson));
            // scalingGroupName, policiesCount
            $scope.scalingGroupName = options.scaling_group_name;
            $scope.policiesCount = options.policies_count;
            $scope.terminationPoliciesUpdate = options.termination_policies;
            $scope.terminationPoliciesOrder = options.termination_policies;
            $scope.availabilityZones = options.availability_zones;
            $scope.setInitialValues();
            $scope.initChosenSelectors();
            $scope.setWatch();
            $scope.setFocus();
            $timeout(function () {  // timeout needed to prevent childNodes lookup error
                $scope.revealModal();
            }, 100);
        };
        $scope.handleSizeChange = function () {
            $scope.isNotChanged = false;
            // Adjust desired/max based on min size change
            if ($scope.desiredCapacity < $scope.minSize) {
                $scope.desiredCapacity = $scope.minSize;
            }
            if ($scope.maxSize < $scope.desiredCapacity) {
                $scope.maxSize = $scope.desiredCapacity;
            }
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
        $scope.watchCapacityEntries = function () {
            var entries = ['minSize', 'maxSize', 'desiredCapacity'];
            angular.forEach(entries, function (item) {
                $scope.$watch(item, function(newVal, oldVal) {
                    if (newVal) {
                        $scope[item] = eucaNumbersOnly(newVal);
                        $scope.isNotValid = false;
                    } else {
                        $scope.isNotValid = true;
                    }
                });
            });
        };
        $scope.setWatch = function () {
            $scope.watchCapacityEntries();
            $scope.$watch('terminationPoliciesUpdate', function (newVal, oldVal) {
                // timeout is needed to ensure the chosen widget to complete its update
                $timeout(function (){
                    // When the termination policies chosen widget is updated, retreive the order the elements displayed
                    $scope.updateTerminationPoliciesOrder(); 
                    // Using the updated termination policies array to re-arrange the options in the select element
                    $scope.rearrangeTerminationPoliciesOptions($scope.terminationPoliciesOrder);
                    $scope.isNotValid = !newVal || (newVal.length === 0 && oldVal.length > 0);
                });
            }, true);
            $scope.$watch('vpcSubnets', function (newVal, oldVal) {
                $scope.disableVPCSubnetOptions();
                $scope.isNotValid = !newVal || (newVal.length === 0 && oldVal.length > 0);
            }, true);
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
            $(document).on('submit', '[data-reveal] form', function () {
                $(this).find('.dialog-submit-button').css('display', 'none');                
                $(this).find('.dialog-progress-display').css('display', 'block');                
            });
            $(document).on('change', 'input[type="number"]', function () {
                var input = $(this);
                if (/^\d+$/.test(input.val())) {
                    $scope.isNotValid = false;
                }
                $scope.isNotChanged = false;
                $scope.$apply();
            });
            $(document).on('change', 'select', function () {
                $scope.isNotChanged = false;
                $scope.$apply();
            });
            // Handle the unsaved tag issue
            $(document).on('submit', '#scalinggroup-detail-form', function(event) {
                $('input.taginput[type!="checkbox"]').each(function(){
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
        };
        $scope.setFocus = function () {
            $(document).on('ready', function(){
                $('.tabs').find('a').get(0).focus();
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
                    var modalLink = modal.find('a').get(0);
                    if (!!inputElement) {
                        inputElement.focus();
                    } else if (!!modalButton) {
                        modalButton.focus();
                    } else if (!!modalLink) {
                        modalLink.focus();
                    }
               }
            });
        };
        $scope.revealModal = function () {
            var thisKey = "do-not-show-nextstep-for-" + $scope.scalingGroupName;
            if ($scope.policiesCount === 0 && Modernizr.localstorage && localStorage.getItem(thisKey) != "true") {
                var modal = $('#nextstep-scalinggroup-modal');
                modal.foundation('reveal', 'open');
                modal.on('click', '.close-reveal-modal', function(){
                    if (modal.find('input#check-do-not-show-me-again').is(':checked')) {
                        if (Modernizr.localstorage) {
                            localStorage.setItem(thisKey, "true");
                        }
                    }
                });
            }
        };
        // Update the termination policies options order
        $scope.updateTerminationPoliciesOrder = function() {
            // Retreive the order of the listed temination policies from the chosen widget
            var orderArray = $.map($('#termination_policies_chosen .search-choice'), function(choice){
                return $(choice).find('a.search-choice-close').first().data('optionArrayIndex');
            });
            // Using the index order array above to construct the actual termination policy array in order
            var options = $('#termination_policies').find('option');
            $scope.terminationPoliciesOrder = $.map(orderArray, function(index) {
                return $(options[index]).val();     
            });
        };
        // Reorder the termination policies selection options
        $scope.rearrangeTerminationPoliciesOptions = function(policies) {
            var select = $('#termination_policies');
            var options = select.find('option');
            if (options.length === 0 ) {
                return;
            }
            // create an array of option elements that maps the order of input array 'policies' 
            var newOptions = $.map(policies, function(policy) {
                var mapped = '';
                angular.forEach(options, function(option) {
                    if ($(option).val() === policy) {
                        mapped = option;
                    } 
                });
                return mapped;
            });
            // appending duplicated elements into select will sort the items in order
            select.append(newOptions); 
            // after rearrange the order of the options, set the values on the select element
            select.val(policies);
            // update the chosen widget if it has been initialized on #termination_policies
            if ($('#termination_policies_chosen').length > 0) {
                select.trigger('chosen:updated');
            }
        };
        // Disable the vpc subnet options if they are in the same zone as the selected vpc subnets
        $scope.disableVPCSubnetOptions = function () {
            $('#vpc_subnet').find('option').each(function() {
                var vpcSubnetID = $(this).attr('value');
                var isDisabled = false;
                angular.forEach($scope.vpcSubnets, function (subnetID) {
                    if ($scope.vpcSubnetZonesMap[vpcSubnetID] == $scope.vpcSubnetZonesMap[subnetID]) {
                        if (vpcSubnetID != subnetID) {
                            isDisabled = true;
                        }
                    }
                }); 
                if (isDisabled) {
                    $(this).attr('disabled', 'disabled'); 
                } else {
                    $(this).removeAttr('disabled');
                }
            });
            // Timeout is need for the chosen widget to react after Angular has updated the option list
            $timeout(function() {
                $('#vpc_subnet').trigger('chosen:updated');
            }, 500);
        };
        // Initialize VPC subnet availablity zone map 
        $scope.createVPCSubnetZonesMap = function () {
            $scope.vpcSubnetZonesMap = {};
            $('#vpc_subnet').find('option').each(function() {
                var vpcSubnetID = $(this).attr('value');
                if (vpcSubnetID !== null) {
                    var vpcSubnetString = $(this).text();
                    var splitArray = vpcSubnetString.split(' ');
                    $scope.vpcSubnetZonesMap[vpcSubnetID] = splitArray[splitArray.length-1];
                }
            });
        };
        // Set the initial values for VPCSubnets array from #vpc_subnet select options
        $scope.setInitialVPCSubnets = function () {
            $scope.vpcSubnets = [];
            $('#vpc_subnet').find('option').each(function() {
                var vpcSubnetID = $(this).attr('value');
                if ($(this).attr('selected')) {
                    $scope.vpcSubnets.push(vpcSubnetID);
                }
            });
        };
    })
;

